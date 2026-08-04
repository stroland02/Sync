# 3D graph view — deferred

This directory is empty on purpose. The M4 dashboard plan installs `three`,
`@react-three/fiber`, and `@react-three/drei` in the scaffolding task so the
dependency tree never has to be rebuilt later, but the components that use
them belong to a later slice of the plan, not this one.

If you're looking at an empty directory and wondering whether something got
skipped: nothing did. The 3D graph view has not been built yet.
