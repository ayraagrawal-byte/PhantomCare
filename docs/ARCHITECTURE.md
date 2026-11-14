# Architecture

```mermaid
flowchart LR
    CMS[CMS enrollment and owner CSVs] --> Import[Validated import]
    Import --> Normalize[Address normalization]
    Normalize --> Buildings[Physical building groups]
    Buildings --> Cluster[County clustering baseline]
    Costar[Local CoStar extract] --> Match[Exact address match]
    Buildings --> Match
    Import --> Owners[Masked ownership graph]
    Cluster --> Indicators[Deterministic indicators]
    Match --> Indicators
    Owners --> Indicators
    Indicators --> Score[Versioned review score]
    Score --> API[Validated FastAPI artifacts]
    Score --> Cases[Evidence-bound case workflow]
    Cases --> API
    API --> UI[Next.js review dashboard]
```

The scoring and investigation layers are deterministic. Missing sponsor data is represented explicitly and available weights are rebalanced. Case findings can only use attached evidence records and fixed neutral language. The dashboard and APIs display screening priorities, not fraud conclusions.
