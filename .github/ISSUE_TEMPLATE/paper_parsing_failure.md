---
name: Paper Parsing Failure
about: Report a PDF parsing, metadata extraction, or text extraction issue
title: "parser: "
labels: ["parser", "bug", "needs-triage"]
assignees: ""
---

## Summary

Describe the parsing failure.

## Paper Information

- Title:
- DOI:
- Source URL, if public:
- Is the PDF legally shareable? yes / no / unknown

## Failure Type

- [ ] Import failed
- [ ] Title extraction incorrect
- [ ] Author extraction incorrect
- [ ] Abstract extraction incorrect
- [ ] DOI extraction incorrect
- [ ] Text extraction incomplete
- [ ] Page or word count incorrect
- [ ] Other

## Command

```bash
poetry run ke import path/to/paper.pdf
```

## Output

```text
Paste relevant output here.
```

## Notes

Do not attach copyrighted PDFs unless redistribution is allowed.
