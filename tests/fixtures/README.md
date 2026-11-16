# Test fixtures (SIMULATED)

Tiny files in the exact CORDIS export format (`;`-separated, every field quoted), with **invented** projects and
organisations. They reproduce the problems found when profiling the real files, so the pipeline can be tested in CI
without downloading CORDIS:

- an objective that starts with an unescaped quote and contains a stray `";"` separator;
- amounts with a decimal comma (`1000000,50`) and a decimal point (`600000.5`);
- a total cost of `0` (not reported), EU country codes `EL` and `UK`, a multi-valued country `DE;HU`, Kosovo `XK`;
- an associated partner with empty contributions, an affiliated entity (thirdParty) funded only in the net column;
- an organisation that leaves and re-joins a project, an SME status that changes between projects;
- a duplicate organisation candidate (same name, different PIC), a duplicate web link, an unclassified project;
- personal and address columns (street, post code, VAT number, coordinates, contact form) that must not reach the database.
