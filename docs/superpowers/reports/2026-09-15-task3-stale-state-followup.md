# Task 3 Stale State Follow-up

## Change

`interaction_observation` commits validate that the existing state is derived from active session and plan facts, but never replace it. A stale state therefore fails closed before publication; a consistent state is left byte-for-byte unchanged.

## Regression coverage

The commit test now:

1. Commits a session fact.
2. Deliberately changes `state.process.recorded_sessions` to make `state.json` stale.
3. Attempts to commit an interaction observation.
4. Asserts validation fails, no observation is published, and `state.json` bytes are unchanged.

## Verification

- Focused: 2 tests passed.
- Full: `python3 -m unittest discover -v` passed, 204 tests.
