---
name: github-issue-to-pr
description: Work on one GitHub issue at a time, only modifying files referenced in the issue, then create a PR with clear notes. Use when asked to implement a specific GitHub issue.
---

# GitHub Issue to PR Workflow

## Purpose

Implement exactly one GitHub issue at a time with strict scope control.

## Required Inputs

The user must provide either:
- a GitHub issue number, e.g. `INFRA-001` or `#12`
- or a GitHub issue URL

If the issue is ambiguous, ask for clarification before making changes.

## Core Rules

- Work only on the specified issue.
- Read the issue before making changes.
- Only modify files explicitly referenced in the issue.
- If the issue does not list allowed files, stop and ask the user to clarify.
- Do not redesign architecture.
- Do not introduce new dependencies unless the issue explicitly allows it.
- Do not work on future issues.
- Do not implement out-of-scope improvements.
- Do not modify unrelated documentation.
- Do not commit secrets.
- Do not store raw customer data.
- Follow CLAUDE.md.

## Required Workflow

1. Confirm clean working tree:
   - Run `git status`.
   - If there are uncommitted changes, stop and ask the user.

2. Fetch the issue:
   - Use `gh issue view <issue-number> --comments`.
   - Summarize objective, scope, allowed files, acceptance criteria, and out-of-scope items.

3. Create a branch:
   - Use branch format:
     `issue/<issue-number>-short-title`
   - Example:
     `issue/infra-001-repo-skeleton`

4. Plan:
   - List the exact files that will be modified.
   - Confirm they are allowed by the issue.
   - If not allowed, stop.

5. Implement:
   - Modify only approved files.
   - Keep implementation minimal.
   - Prefer functional Python.
   - Use clear comments only where intent is non-obvious.

6. Validate:
   - Run only relevant tests/checks.
   - If tests are unavailable, document that clearly.

7. Review changes:
   - Run `git diff`.
   - Confirm no unrelated files changed.

8. Commit:
   - Use commit message format:
     `<ISSUE-ID>: <short description>`
   - Example:
     `INFRA-001: create repository skeleton`

9. Push branch:
   - `git push -u origin <branch-name>`

10. Create PR:
   - Use `gh pr create`.
   - PR title:
     `<ISSUE-ID>: <short title>`
   - PR body must include:
     - Summary
     - Files changed
     - Validation performed
     - Scope confirmation
     - Issue link

11. Do NOT merge automatically unless the user explicitly asks.

12. Do NOT close the issue automatically unless the PR is merged and the user explicitly asks.

## PR Body Template

```md
## Summary

- ...

## Files Changed

- ...

## Validation

- [ ] Relevant checks/tests run
- [ ] No unrelated files changed
- [ ] No new dependencies added unless approved
- [ ] No secrets or raw customer data committed

## Scope Confirmation

This PR only addresses the referenced issue and only modifies files allowed by the issue.

## Linked Issue

Closes #<issue-number>
Stop Conditions

Stop and ask the user if:

the working tree is dirty
the issue does not specify allowed files
implementation requires files not listed in the issue
a new dependency seems necessary
architecture changes are required
tests fail and the fix is outside issue scope