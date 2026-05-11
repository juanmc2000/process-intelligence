"""Process similarity and clustering engine.

Provides deterministic similarity scoring between ProcessIR instances,
fingerprint generation, alias detection, and candidate clustering.

All logic is purely algorithmic — no database, API, storage, or LLM dependencies.
Similarity is computed on sets of canonical labels extracted from ProcessIR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from packages.core.schemas.process_ir import ProcessIR


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcessFingerprint:
    """Compact, hashable representation of a ProcessIR's structural content.

    Built from canonical label sets so two ProcessIR instances that describe
    the same operational workflow produce similar (or identical) fingerprints
    even when authored independently.
    """

    process_id: str
    # Frozen sets of lower-cased canonical labels per dimension
    step_labels: frozenset[str]
    role_labels: frozenset[str]
    system_labels: frozenset[str]
    control_labels: frozenset[str]
    change_labels: frozenset[str]
    exception_labels: frozenset[str]

    @property
    def is_empty(self) -> bool:
        """True when the fingerprint has no content in any dimension."""
        return (
            not self.step_labels
            and not self.role_labels
            and not self.system_labels
            and not self.control_labels
        )


def make_fingerprint(process_ir: ProcessIR) -> ProcessFingerprint:
    """Build a ProcessFingerprint from a ProcessIR instance.

    Each dimension is a frozenset of normalised (lower-cased, stripped) labels.
    """
    return ProcessFingerprint(
        process_id=process_ir.id,
        step_labels=frozenset(
            s.name.lower().strip() for s in process_ir.workflow_steps
        ),
        role_labels=frozenset(r.name.lower().strip() for r in process_ir.roles),
        system_labels=frozenset(
            t.system_name.lower().strip() for t in process_ir.system_touchpoints
        ),
        control_labels=frozenset(c.name.lower().strip() for c in process_ir.controls),
        change_labels=frozenset(
            e.name.lower().strip() for e in process_ir.change_events
        ),
        exception_labels=frozenset(
            x.name.lower().strip() for x in process_ir.exceptions
        ),
    )


# ---------------------------------------------------------------------------
# Jaccard helpers
# ---------------------------------------------------------------------------


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity between two sets.  Returns 1.0 if both are empty."""
    if not a and not b:
        # Two processes with no entries in a dimension are equally absent.
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


# Relative weight per dimension for the composite score.
# Workflow steps carry the most signal; changes / exceptions are secondary.
_WEIGHTS: dict[str, float] = {
    "steps": 0.40,
    "roles": 0.20,
    "systems": 0.20,
    "controls": 0.10,
    "changes": 0.05,
    "exceptions": 0.05,
}


# ---------------------------------------------------------------------------
# Similarity score
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Jaccard score for a single structural dimension."""

    dimension: str
    score: float
    overlap: list[str]  # labels in common


@dataclass
class SimilarityScore:
    """Composite similarity result between two ProcessIR fingerprints."""

    process_id_a: str
    process_id_b: str
    score: float  # weighted composite in [0, 1]
    dimensions: list[DimensionScore]
    explanation: str

    @property
    def is_likely_same_process(self) -> bool:
        """Heuristic: processes with score >= 0.70 are probably the same."""
        return self.score >= 0.70

    @property
    def is_likely_alias(self) -> bool:
        """Heuristic: high role/system overlap but lower step overlap suggests alias."""
        role_score = next(
            (d.score for d in self.dimensions if d.dimension == "roles"), 0.0
        )
        system_score = next(
            (d.score for d in self.dimensions if d.dimension == "systems"), 0.0
        )
        return (role_score + system_score) / 2 >= 0.80 and self.score >= 0.50


def score_similarity(a: ProcessFingerprint, b: ProcessFingerprint) -> SimilarityScore:
    """Compute a weighted composite Jaccard similarity between two fingerprints.

    Each dimension is scored separately so the explanation is fully transparent.
    """
    dims: list[tuple[str, frozenset[str], frozenset[str], float]] = [
        ("steps", a.step_labels, b.step_labels, _WEIGHTS["steps"]),
        ("roles", a.role_labels, b.role_labels, _WEIGHTS["roles"]),
        ("systems", a.system_labels, b.system_labels, _WEIGHTS["systems"]),
        ("controls", a.control_labels, b.control_labels, _WEIGHTS["controls"]),
        ("changes", a.change_labels, b.change_labels, _WEIGHTS["changes"]),
        ("exceptions", a.exception_labels, b.exception_labels, _WEIGHTS["exceptions"]),
    ]

    dimension_scores: list[DimensionScore] = []
    composite = 0.0
    for name, set_a, set_b, weight in dims:
        j = _jaccard(set_a, set_b)
        overlap = sorted(set_a & set_b)
        composite += j * weight
        dimension_scores.append(
            DimensionScore(dimension=name, score=round(j, 4), overlap=overlap)
        )

    composite = round(composite, 4)
    explanation = _build_explanation(composite, dimension_scores)

    return SimilarityScore(
        process_id_a=a.process_id,
        process_id_b=b.process_id,
        score=composite,
        dimensions=dimension_scores,
        explanation=explanation,
    )


def _build_explanation(composite: float, dims: list[DimensionScore]) -> str:
    """Build a human-readable explanation for a similarity score."""
    top = sorted(dims, key=lambda d: d.score, reverse=True)
    drivers = [f"{d.dimension}={d.score:.2f}" for d in top[:3]]
    shared = [d for d in dims if d.overlap]
    shared_summary = (
        f" Shared labels: {', '.join(d.overlap[0] for d in shared[:3])}."
        if shared
        else ""
    )
    return f"Composite score {composite:.2f}. Top drivers: {', '.join(drivers)}.{shared_summary}"


# ---------------------------------------------------------------------------
# Alias detection
# ---------------------------------------------------------------------------


@dataclass
class AliasGroup:
    """A set of process IDs that likely refer to the same operational process."""

    canonical_id: str  # the 'primary' representative (first encountered)
    alias_ids: list[str]  # other process IDs in this alias group
    similarity_scores: list[SimilarityScore]


def detect_aliases(
    fingerprints: list[ProcessFingerprint],
    alias_threshold: float = 0.80,
) -> list[AliasGroup]:
    """Find groups of fingerprints that likely represent the same process.

    Two processes are considered aliases when their composite similarity
    exceeds alias_threshold.  Uses union-find to merge transitive aliases.

    Args:
        fingerprints: List of ProcessFingerprint to compare.
        alias_threshold: Minimum composite score to treat two processes as aliases.

    Returns:
        List of AliasGroup (groups with 2+ members only).
    """
    scores: list[SimilarityScore] = []
    pairs: list[tuple[int, int]] = []

    for i in range(len(fingerprints)):
        for j in range(i + 1, len(fingerprints)):
            s = score_similarity(fingerprints[i], fingerprints[j])
            scores.append(s)
            if s.score >= alias_threshold:
                pairs.append((i, j))

    # Union-find grouping
    parent = list(range(len(fingerprints)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i, j in pairs:
        union(i, j)

    # Build groups
    groups: dict[int, list[int]] = {}
    for idx in range(len(fingerprints)):
        root = find(idx)
        groups.setdefault(root, []).append(idx)

    # Collect alias scores for each group
    score_map: dict[tuple[str, str], SimilarityScore] = {
        (s.process_id_a, s.process_id_b): s for s in scores
    }

    result: list[AliasGroup] = []
    for root, members in groups.items():
        if len(members) < 2:
            continue
        fps = [fingerprints[m] for m in members]
        canonical = fps[0]
        aliases = [f.process_id for f in fps[1:]]
        group_scores = [
            score_map.get((canonical.process_id, aid))
            or score_map.get((aid, canonical.process_id))
            for aid in aliases
        ]
        result.append(
            AliasGroup(
                canonical_id=canonical.process_id,
                alias_ids=aliases,
                similarity_scores=[s for s in group_scores if s is not None],
            )
        )

    return result


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


@dataclass
class ProcessCluster:
    """A group of related ProcessIR fingerprints with similarity metadata."""

    cluster_id: str
    # process IDs in this cluster (canonical first)
    process_ids: list[str]
    # Pairwise scores within the cluster
    intra_scores: list[SimilarityScore]
    # Average intra-cluster similarity
    cohesion: float
    # Recommended merge: True when average score >= merge_threshold
    recommend_merge: bool
    merge_note: Optional[str] = None


def cluster_processes(
    fingerprints: list[ProcessFingerprint],
    similarity_threshold: float = 0.50,
    merge_threshold: float = 0.80,
) -> list[ProcessCluster]:
    """Group fingerprints into similarity clusters using single-linkage agglomeration.

    Two processes enter the same cluster when their similarity >= similarity_threshold.
    Within a cluster, if average pairwise similarity >= merge_threshold the cluster
    carries a merge recommendation.

    Args:
        fingerprints: List of fingerprints to cluster.
        similarity_threshold: Minimum score for two processes to share a cluster.
        merge_threshold: Minimum average intra-cluster score to flag merge.

    Returns:
        List of ProcessCluster, one per connected component.
    """
    n = len(fingerprints)
    if n == 0:
        return []

    # Compute all pairwise scores
    all_scores: dict[tuple[int, int], SimilarityScore] = {}
    for i in range(n):
        for j in range(i + 1, n):
            s = score_similarity(fingerprints[i], fingerprints[j])
            all_scores[(i, j)] = s

    # Single-linkage union-find
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for (i, j), s in all_scores.items():
        if s.score >= similarity_threshold:
            union(i, j)

    # Build clusters
    groups: dict[int, list[int]] = {}
    for idx in range(n):
        root = find(idx)
        groups.setdefault(root, []).append(idx)

    clusters: list[ProcessCluster] = []
    for cluster_num, (root, members) in enumerate(sorted(groups.items())):
        fps = [fingerprints[m] for m in members]
        pids = [f.process_id for f in fps]

        # Collect intra-cluster pairwise scores
        intra: list[SimilarityScore] = []
        for mi in range(len(members)):
            for mj in range(mi + 1, len(members)):
                i, j = members[mi], members[mj]
                key = (min(i, j), max(i, j))
                if key in all_scores:
                    intra.append(all_scores[key])

        cohesion = round(sum(s.score for s in intra) / len(intra), 4) if intra else 1.0
        recommend = cohesion >= merge_threshold

        clusters.append(
            ProcessCluster(
                cluster_id=f"cluster_{cluster_num + 1}",
                process_ids=pids,
                intra_scores=intra,
                cohesion=cohesion,
                recommend_merge=recommend,
                merge_note=(
                    "High intra-cluster similarity — candidate for deduplication."
                    if recommend
                    else None
                ),
            )
        )

    return clusters
