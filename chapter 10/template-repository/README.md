# Governed Agent Template

This is the small template repository described in Chapter 10. Every behavior-changing input is either baked into the image or named immutably by `bundle.yaml`. Runtime configuration, session state, and credentials remain outside the image.

`maintenance_agent.py` is the deliberately thin, stateless container entry point. It reads the immutable bundle from disk and runtime routing, gateway, and workload identity from the environment. It never accepts serialized run state or a long-lived credential.

From the parent `chapter 10` directory, run the same release gate used by CI:

```bash
python -m chapter10 --pipeline-only --gate-mode block --output-dir artifacts
```

The checked-in reports are synthetic and offline. A production pipeline replaces them with repeated golden-set runs, preserves the same report contract, signs the image and provenance with the organization's build identity, and makes the named gate a required git-host check.
