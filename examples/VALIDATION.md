# Validation record

Version 0.1.0 was checked locally with Python 3.12 and real Chromium (installed Chrome) in an isolated headless browser profile.

- 20 automated tests passed, including direct-build gate enforcement, all five sensitive-pattern classes, import rollback, first-use links, locale fallback and Chinese index segmentation.
- README installation/check/preview workflow ran successfully. Strict static build passed.
- Desktop 1440 x 1000 and mobile 390 x 844 were visually inspected. The mobile language menu was repositioned to prevent horizontal overflow.
- Browser exercised glossary filtering, timeline filtering and expansion, term navigation, secondary locale banner and Chinese search. Chinese query returned two matching glossary documents across the two locale routes.
- No JavaScript errors or external runtime requests remained. A template override removes Material's automatic repository-statistics requests. Development live reload remains local.

Screenshots are in `screenshots/`. The content is fictional and English, except the intentional Chinese search terms. The design uses Material's navigation, typography and search with a restrained teal palette and a responsive three-card overview.
