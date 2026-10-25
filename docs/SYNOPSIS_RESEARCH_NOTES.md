# Synopsis research notes

These notes support the literature review and methodology in the AccessPath AI synopsis. Claims are based on primary standards, official tool documentation, and original research papers.

## Standards and evaluation guidance

- W3C, *Web Content Accessibility Guidelines 2.2*: WCAG 2.2 defines testable success criteria for accessible web content. The project initially focuses on keyboard-related criteria such as Keyboard, No Keyboard Trap, Focus Order, Focus Visible, and Focus Not Obscured. https://www.w3.org/TR/WCAG22/
- W3C, *WCAG Evaluation Methodology 2.0*: WCAG-EM describes a structured evaluation process: define scope, explore the product, select a representative sample, evaluate it, and report findings. It also recommends involving users with disabilities. https://www.w3.org/TR/WCAG-EM/
- W3C, *Understanding Success Criterion 2.1.1 Keyboard*: functionality should be operable through a keyboard interface without requiring timed keystrokes, except for genuinely path-dependent functions. https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html

## Automated accessibility testing

- Deque Systems, *axe-core*: axe-core applies rule-based checks to rendered HTML interfaces. Its official README states that it finds an average of 57% of WCAG issues automatically and marks uncertain cases as incomplete for manual review. https://github.com/dequelabs/axe-core
- Vigo, Brown, and Conway (2013), *Benchmarking web accessibility evaluation tools*: the study compared six tools and warned that sole reliance on automated tests can leave important accessibility barriers undetected. DOI: https://doi.org/10.1145/2461121.2461124
- Ara, Sik-Lanyi, and Kelemen (2024), *Accessibility engineering in web evaluation process*: the systematic review examined 92 primary studies and organized methods, tools, techniques, and gaps across the accessibility evaluation process. DOI: https://doi.org/10.1007/s10209-023-00967-2
- Pool (2023), *Accessibility Metatesting*: nine automated tools were applied to 121 pages. Each tool found issues missed by the others, showing complementary rather than complete coverage. DOI: https://doi.org/10.1145/3587281.3587282

## AI and LLM based accessibility evaluation

- Lopez-Gil and Pereira (2025), *Turning manual web accessibility success criteria into automatic*: LLM-based scripts evaluated three WCAG criteria that normally need human judgment and reported 87.18% detection across the study test cases. The work supports LLM-assisted evaluation but covers selected criteria rather than journey completion. DOI: https://doi.org/10.1007/s10209-024-01108-z
- Vera-Amaro and Rojano-Caceres (2025), *Towards accessible website design through artificial intelligence*: a systematic review screened 277 studies and retained 31 key works. AI use was concentrated in alternative text, compliance assessment, remediation suggestions, and interface generation; inconsistent compliance and limited attention beyond specific code cases remained concerns. DOI: https://doi.org/10.1016/j.infsof.2025.107821
- Aljedaani and Mollik (2026), *Large Language Models for Web Accessibility*: the review of 38 peer-reviewed studies found concentration on text-centric and structurally explicit problems, varied evaluation methods, and limited direct involvement of people with disabilities. DOI: https://doi.org/10.1145/3800424.3800452
- Yepes-Parra and Escobar-Velasquez (2025), *Autonomous Agents for Accessibility*: this emerging agent framework argues that static analysis misses real-time interaction problems and proposes agents that interact through keyboard and screen-reader modalities. DOI: https://doi.org/10.1109/ASE63991.2025.00349

## Method support

- Playwright keyboard API: Playwright can issue real keyboard events such as Tab, Enter, Space, arrow keys, and typed text. https://playwright.dev/docs/api/class-keyboard
- Playwright accessibility guidance: automated scans find some common problems, but the official guidance recommends combining automation, manual assessment, and inclusive user testing. https://playwright.dev/docs/accessibility-testing

## Defensible research positioning

The project should not claim to be the first use of AI for accessibility. The defensible contribution is the combination of:

1. goal-driven, keyboard-only completion of a multi-step task;
2. an AI planner restricted to a small action schema;
3. deterministic policy validation before each browser action;
4. completion and barrier decisions based on declared observable conditions;
5. step-level screenshots, focus state, actions, and outcome evidence; and
6. controlled accessible and deliberately broken journey variants for repeatable evaluation.

The current study remains a prototype evaluation. It does not establish full WCAG conformance, replace expert assessment, or substitute for testing with people with disabilities.
