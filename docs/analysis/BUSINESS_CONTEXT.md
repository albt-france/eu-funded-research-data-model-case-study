# Business context: how a Horizon Europe project is run

What the data describes, before modelling it. Facts are taken from the official texts (links below, read on
17 November 2026) and summarised, not copied. This is a description of the process; it gives no advice to applicants.

## The programme

- **Horizon Europe** is the EU research and innovation framework programme for **2021-2027**, established by
  [Regulation (EU) 2021/695](https://eur-lex.europa.eu/eli/reg/2021/695/oj). Its predecessor was **Horizon 2020**
  (2014-2020, [Regulation (EU) No 1291/2013](https://eur-lex.europa.eu/eli/reg/2013/1291/oj)).
- **Structure (Article 4):** Pillar I *Excellent Science* (ERC, Marie Skłodowska-Curie Actions, research
  infrastructures); Pillar II *Global Challenges and European Industrial Competitiveness* (six clusters, e.g. Health;
  Climate, Energy and Mobility; Digital, Industry and Space); Pillar III *Innovative Europe* (European Innovation Council,
  innovation ecosystems, EIT); and a part *Widening Participation and Strengthening the European Research Area*.
  In CORDIS this hierarchy is the **legal basis** of each project (e.g. `HORIZON.2.5` = Climate, Energy and Mobility).
- **Budget (Article 12):** EUR 86.1 billion in current prices for the specific programme and the EIT, split by pillar
  in Article 12(2) (Pillar II has the largest share, EUR 47.4 billion).

## Life cycle of a project

| Step | What happens | Main actor | Where it appears in CORDIS |
|---|---|---|---|
| 1. Work programme and **call** | The Commission publishes calls; each call has **topics**, the unit a proposal answers. | European Commission / agency | `masterCall`, `topics` |
| 2. **Consortium** and **proposal** | Organisations register (each legal entity gets a **PIC**, Participant Identification Code) and submit one proposal through the Funding & Tenders Portal. | Applicants, future coordinator | `organisationID` (PIC) |
| 3. **Eligibility** | Collaborative actions need at least three independent legal entities, from three different Member States or associated countries, with at least one in a Member State (Article 22(2)). ERC, MSCA fellowships, EIC and coordination actions can have a single beneficiary (Article 22(3)-(4)). | Agency | consortium size per project |
| 4. **Evaluation** | Independent external experts (Article 29) score three award criteria: **excellence, impact, quality and efficiency of the implementation** (Article 28(1)); ERC frontier research is evaluated on excellence only. | Expert evaluators | not published (only funded projects are) |
| 5. **Grant preparation and signature** | The coordinator submits the grant data and the description of the action; reporting periods and pre-financing are set. Applicants are informed within **5 months** and grants are signed within **8 months** of the call deadline (Article 31(1)). | Coordinator, agency | `ecSignatureDate`, `ecMaxContribution` |
| 6. **Implementation** | The consortium carries out the work; deliverables and milestones are submitted. Beneficiaries can be joined by **affiliated entities** and **associated partners** (the latter without EU funding). | Coordinator, beneficiaries | roles, `webLink` deliverables |
| 7. **Reporting** | At the end of each **reporting period**, a periodic report (technical part + financial statements) is submitted by the coordinator, normally within 60 days. | Coordinator | not in open data |
| 8. **Payments** | Pre-financing at the start; interim payments after each accepted periodic report (paid to the coordinator within 90 days, up to 90% of the maximum grant before the end); the balance after the final report. | Agency → coordinator → beneficiaries | not in open data (CORDIS gives the maximum grant) |
| 9. **Closure** | The project ends as CLOSED, or TERMINATED if it stopped early; checks, reviews and audits can follow. | Agency | `status` |

**Funding rules used to read the data:** up to 100% of eligible costs for research and innovation actions, up to 70% for
innovation actions except non-profit entities (Article 34(2)); indirect costs at a 25% flat rate (Article 35(1)).
Many grants are **lump sums or unit costs** (e.g. MSCA fellowships): CORDIS then reports no total cost (see
[DATA_PROFILING.md](DATA_PROFILING.md)).

## Actors and roles

| Actor | Role in the process | In the data model |
|---|---|---|
| Granting authority (Commission or executive agency) | publishes calls, evaluates, signs, pays, monitors | not a table (one per programme part in practice) |
| Expert evaluator | scores proposals | out of scope (no public data) |
| **Coordinator** | single contact point, submits reports, receives payments and distributes them | `participation.role_code = 'coordinator'` (exactly one per project) |
| **Beneficiary** | signs the grant, does the work, receives EU funding | `participant` |
| **Affiliated entity** | linked to a beneficiary, declares costs through it | `thirdParty` (funded in the *net* contribution) |
| **Associated partner** | takes part without EU funding | `associatedPartner` (Horizon Europe), `partner` and `internationalPartner` (H2020) |
| Programme manager / analyst | follows the portfolio: funding by country, domain, organisation type | the users of the analytical model |

## Sources

- Regulation (EU) 2021/695 establishing Horizon Europe: Articles 4, 12, 22, 28, 29, 31, 34, 35.
  https://eur-lex.europa.eu/eli/reg/2021/695/oj
- EU Funding & Tenders Portal, Online Manual: evaluation, grant preparation, reports and payment requests.
  https://webgate.ec.europa.eu/funding-tenders-opportunities/display/OM/Online+Manual
- CORDIS - EU research projects under Horizon Europe (2021-2027), Publications Office of the EU, reuse under
  Commission Decision 2011/833/EU. https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip
