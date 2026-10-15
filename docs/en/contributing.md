---
translation_status: complete
---

# Contributing

Write for readers who need to verify your claims.

## Add a page

Run `kbtool new-page example-topic --section principles`. It creates both locale slots, with the secondary slot marked pending. Add the page to the navigation in `mkdocs.yml`.

## Cite and translate

Keep sources in `data/references.yaml`; cite one with the syntax shown in the repository README. Keep terminology in the five-column glossary CSV. Replace English placeholders in the secondary slot only when a reviewed translation is available, then set `translation_status: complete`.

## Check before sharing

Run `kbtool check --json` and `kbtool build`. The rules catch configured patterns in text; they do not replace editorial review of images, PDFs or technical claims. A deliberate, reviewed exception uses the same-line comment `<!-- kb-allow -->`.

## Licenses

Code is MIT licensed. Sample content and documentation are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribute the project when adapting content. All topic examples are fictional placeholders.
