# Historical transcription planning fixture

`transcription-task-catalog.txt` is the unmodified task catalog recovered from EVORA commit `114c3824a40cfd36e04f22b9d7a61f01e8fd6ddb` (`docs/TASK_BREAKDOWN.md`). It preserves the original checkpoint/dependency mutation tests after that planning document was removed from the product checkout. It is test data, not the current project roadmap or evidence that any feature works.

`legacy-coordination/` preserves the original coordination documents, fixtures and 27-operation contract from the same commit for the main repo's additional legacy CLI/ledger tests. It is historical test data. Product contract checks still validate the current `specs/openapi.yaml`; CLI regressions run the current helper with an explicit historical-contract option.
