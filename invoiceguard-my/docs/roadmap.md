# Implementation roadmap (gated)

| Phase | Duration | Scope | Exit gate |
|---|---|---|---|
| 0 Discovery & baseline | 2 wks | Volume and time study on the real process; data-protection review; pick pilot suppliers | Signed-off baseline and data-handling plan |
| 1 Assisted mode (sandbox) | 4 wks | Extraction + validation + review UI against MyInvois **sandbox** only; human approves 100% | Field accuracy at target; **zero wrong auto-approvals** |
| 2 Shadow pilot | 4 wks | Runs beside the manual process on real invoices; compare outputs | STP at target with wrong-auto-approve ≈ 0 |
| 3 Limited production | 6 wks | Production credentials; auto-approve a low-risk class only; alerts and runbook | Stable error and rework rates; incident drill passed |
| 4 Scale & integrate | 8+ wks | Accounting-system connectors, multi-entity, roles, self-billing flows | Audit review; cost per invoice within target |
| 5 Continuous | ongoing | Rules versioned per LHDN guideline change; model re-evaluation per release | Regression eval passes before every release |

**Risks:** regulatory change (rules versioned in YAML) · model drift (monthly re-eval) · vendor lock-in (swappable extractor) · privacy (PDPA 2010 as amended
`[VERIFY]`, redaction, retention) · over-reliance (mandatory spot checks) · **self-consistent misreads and tolerance trade-offs** (sampling audits; see IG-0075).

**Build vs buy:** many certified accounting packages already issue MyInvois-compliant invoices. Position InvoiceGuard as the **intake, validation and exception
layer** for messy inbound documents, not an ERP replacement.
