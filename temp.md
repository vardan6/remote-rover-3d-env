The physics seems broken, the overall it looks fine, but now I need to make it what it is really intended to be, the rover appears on the ground right, when move forward or backward also seems right. left and right not so good, but so far is ok. But the overall physics is not right. 1. the wheels again ethe can go into the ground when move to one direction, or can de-touch from ground when go to another it seems like the rover moving plane is slightly angled compared to ground plane angle. 2. Overall it seems it need some physics to be implemented to make it real. The ground should have some roughness, maybe it already has it, it is good, but I need also some hills and valleys, not rush with smaller angles. I need some obstacles which are comparable sizes to the rover, maybe stones. I need the rover to run over the ground in close to real way so each wheel touch the ground and rover will change its angle to stay 4 wheels touch the ground any time, at some point it should have gravity, maybe add gravity right now to achieve this reality effect, if it is possible add the suspension right now, or plan for later or consider for later, but I need to have also suspension with the gravity to it can bouncy or springy when move the wheels should be springy, mayc wheel axis may move slightly oner its fixed point compared to rover body. I believe you need to research for better approaches for that, maybe it needs additional libraries or packages ? please do research and see what changes it may need ? 

"1. New files:
   - Rover-3d-model-init-dev-2025-03-16.png - demo video thumbnail
   - phase1-3D-Simulator.md - comprehensive documentation file
2. Modified files:
   - simulator/main.py - Added PCF soft-shadow shader to rover (in addition to terrain)
   - simulator/rover.py - Added per-face normals to the rover body mesh (v3n3c4 format)
   - simulator/shadow_pcf.frag - Adjusted shadow bias from 0.001 to 0.0006
The main changes are:
1. Applied PCF shadow shader to the rover chassis
2. Added proper normals to the rover body geometry for correct lighting
3. Tweaked shadow bias for better shadow quality
This is a focused set of changes related to improving shadow rendering and lighting on the rover.
I should provide a concise commit message that summarizes these changes.
Based on the staged changes, here's a suggested commit message:
Improve rover shadows with per-face normals and PCF shader
- Add per-face normals to rover body geometry (v3n3c4 format) for correct lighting
- Apply PCF soft-shadow shader to rover chassis alongside terrain
- Reduce shadow bias from 0.001 to 0.0006 for cleaner shadow edges
Also adds demo screenshot and comprehensive documentation (phase1-3D-Simulator.md)."


claude --verbose --continue
claude --verbose --resume 17a38148-095a-4f50-b4c6-f203116b2287

please raed and understand this project, possibly the top level files are: '/mnt/c/Users/vardana/Documents/Proj/remote-rover/3d-env/initial-hl-design.md' '/mnt/c/Users/vardana/Documents/Proj/remote-rover/3d-env/phase1-3D-Simulator.md'


# GitHub Actions: Advanced Workflow Architecture — Research Notes

## Context

I was looking into how to build a more modular and reusable CI/CD pipelines in GitHub Actions, where logic like building a product(SmartSpice) is defined once in one workflow file and reused across other workflows. This led me to investigate data-sharing mechanisms: reusable workflow inputs/outputs, upload/download artifacts, and job-level outputs.

## What I Found About the Native Mechanisms

Reusable workflows support formal `inputs` and `outputs`, and job outputs let you pass strings between jobs. Both work, but getting even a single string from a reusable workflow back to the caller requires defining it in three to four separate places in the YAML — at the step, at the job, at the workflow output declaration, and at the caller reference. For multiple values this multiplies quickly and becomes very difficult to maintain.



### Upload/Download Artifacts

Upload and download artifacts are the right tool for actual files — binaries, packages, reports. But using them just to pass a version string or a build path is overkill both in YAML lines and in runtime overhead.
Getting artifact upload and download to actually work required more troubleshooting than expected. Particularly self-hosted runners would fail with TLS certificate errors or connectivity rejections when trying to reach artifact. The fixes I had to apply included:
- Switching between versions of `actions/upload-artifact` and `actions/download-artifact` (v3 vs v4 behave differently in how they handle the storage backend and authentication)
- Setting `NODE_TLS_REJECT_UNAUTHORIZED=0` or similar environment-level flags to bypass certificate verification
- Loosening proxy or network security environment settings

These workarounds(disabling security attributes) carry potential risks, and loosening network security settings may violate organizational policy. They should be treated as temporary debugging steps, not permanent configuration.

### What I Decided to Use

After testing everything, dumping all build metadata into a simple Bash env file and sharing it as a single artifact turned out to be the most practical approach. Downstream jobs download it and either source it directly in scripts or append it to `$GITHUB_ENV`. One upload, one download, any number of variables — no relay chain, no per-variable YAML ceremony.



### Data Exchange: Direction vs Mechanism

| Direction                                  | Filesystem (NFS shared)                                                                                            | `$GITHUB_OUTPUT` / `$GITHUB_ENV`                                                                                                                                                                                                                                                                                                                                                         | Job `outputs:` + `needs:`                                    | `inputs:` / `outputs:` (workflow_call)                                                                                                                           | Upload / Download Artifact                                                                                                        | Bash env file via Artifact                                                                                                     |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Step → Step** (same job)                 | ✅ Same NFS path. Write and read directly.                                                                          | ✅ Primary use. `$GITHUB_ENV` makes a value available to all subsequent steps in the same job. The setting step itself cannot read the new value — only the steps after it can.                                                                                                                                                                                                           | ❌ Not applicable at step level.                              | ❌ Not applicable at step level.                                                                                                                                  | ⚠️ Overkill. NFS and `$GITHUB_ENV` handle this for free.                                                                          | ⚠️ Overkill within a single job.                                                                                               |
| **Job → Job** (same workflow)              | ✅ NFS solves this. Requires `needs:` to guarantee job ordering so the producing job finishes first.                | ❌ Does not work. `$GITHUB_ENV` and `$GITHUB_OUTPUT` are scoped to the job they are set in. A new job gets a fresh runner environment and does not inherit anything written to these files by a previous job. Confirmed by official docs and community.                                                                                                                                   | ✅ Intended use for strings. Requires `needs:`. Strings only. | ❌ Not applicable at this level.                                                                                                                                  | ⚠️ Redundant if NFS is available. Adds unnecessary network overhead.                                                              | ⚠️ Redundant — just write the env file to NFS directly and source it.                                                          |
| **Top-level workflow → Reusable workflow** | ✅ Files on NFS are already visible inside the reusable workflow jobs. No mechanism needed.                         | ❌ Does not work. Environment variables set in the called workflow are not accessible in the `env` context of the caller workflow, and the reverse is also true — `GITHUB_ENV` cannot be used to pass values to job steps across workflow boundaries. [GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations) Use `inputs:` instead. | ❌ Not applicable in this direction.                          | ✅ Intended use. Pass via `with:` at call site. Supports string, number, boolean only.                                                                            | ⚠️ Redundant if NFS is available.                                                                                                 | ⚠️ Redundant — write to NFS path directly.                                                                                     |
| **Reusable workflow → Top-level workflow** | ✅ Files written inside reusable workflow jobs are on the same NFS share, visible to caller's next job immediately. | ❌ Does not work. `GITHUB_ENV` values set inside a reusable workflow do not propagate back to the caller workflow. [GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations) The env context is fully isolated across workflow boundaries in both directions.                                                                          | ❌ Not applicable in this direction.                          | ⚠️ Supported but painful. 4-layer relay chain per value: step → job → workflow output → caller reference. Strings only. NFS makes this avoidable for most cases. | ✅ Works. Upload inside reusable workflow, download in caller's next job. Same TLS/proxy caveats apply in restricted environments. | ✅ Most practical without NFS. With NFS, write the env file to a known path and source it directly — no upload/download needed. |
| **Reusable workflow → Reusable workflow**  | ✅ All levels see the same NFS share. Write once, read anywhere.                                                    | ❌ Does not work. Each reusable workflow is an isolated execution context. Environment variables from one workflow do not extend to a reusable workflow it calls. [GitHub](https://github.com/orgs/community/discussions/26671) Confirmed by both official docs and community reports.                                                                                                    | ❌ Not applicable.                                            | ⚠️ Supported up to 3 nesting levels. Same relay chain verbosity at every level. Gets unmanageable quickly.                                                       | ✅ Works regardless of nesting depth. Artifact availability is run-scoped, not workflow-scoped.                                    | ✅ Cleanest pattern with NFS — write once to a known path, source at any level. No upload/download involved.                    |

---

### Legend

- ✅ Works well
- ⚠️ Works but with caveats, redundancy, or overhead
- ❌ Not possible or not applicable