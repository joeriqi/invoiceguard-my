# Business problem

**Who hurts:** SME finance/admin staff and owner-managers who receive supplier invoices as PDFs, photos and emails and re-key them by hand while
Malaysia's MyInvois e-invoicing regime applies to every business tier.

**Evidence** (source quality: **S** = secondary advisory / vendor blog, **N** = news, **A** = academic preprint). *Everything below must be confirmed against
primary LHDN documents before publication; see `evidence_log.csv`.*

| Claim | Source | Quality |
|---|---|---|
| Phase 4 (RM1M-RM5M turnover) started 1 Jan 2026; penalty-free relaxation reportedly extended to **31 Dec 2027**, enforcement from 1 Jan 2028 | JomeInvoice FAQ / ClearTax citing LHDN guideline v4.7-v4.8 | S |
| Single transactions of **RM10,000 or more cannot be consolidated** | JomeInvoice penalty guide | S |
| Penalties of **RM200-RM20,000 per offence** (plus possible imprisonment) | AppAsia / JomeInvoice | S |
| Almost 1.3M MSMEs are ~96% of businesses and ~39.7% of GDP (2025) | Bernama (DOSM figures) | N |
| Average invoice processing cost ~**US$9.84** (Ardent Partners 2025); APQC median ~US$5.83 (relayed via vendor blogs) | Corpay / Docsumo relays | S |
| Native image input beat text-parsing pipelines for LLM invoice extraction; models struggled with long alphanumeric strings | Berghaus et al., arXiv 2509.04469 | A |
| Reported MyInvois validation change on 24 Oct 2026 (amount fields, passport length) | JomeInvoice FAQ | S |
| RM3M MSME Exemption Threshold (Exemption threshold raised under Guideline v4.8) | LHDN published e-Invoice General Guideline v4.8 | S |

**Why now:** the mandate is live; the relaxation window ends; exceptions and rejections will surface when penalties begin.

**What this repo's own EDA adds** (synthetic corpus, so it describes the *test bench*, not Malaysian SMEs): 46.7% of invoices arrive in the last five days
of the month, 14% are ≥ RM10,000, 42% are scans or photos, 29% carry no MyInvois UIN, and the top five suppliers send 44% of invoices.
