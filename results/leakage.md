# RBAC Leakage Check

Every one of 19 questions queried at **user_clearance = 0**; counted any returned chunk with clearance > 0 (restricted/internal).

- Restricted chunks leaked to a clearance-0 user: **0**
- (of which 5 questions actually require clearance 2 to answer)

**Leakage rate: 0/19 queries → 0% — enforced at retrieval ✅**
