# Issue Description

## Title: False-Positive Code Blocking on Natural Language Text by OutputValidator

### Description
The OutputValidator overly aggressively detects conversational English phrases as "hallucinated code". Any sentence containing common programming keywords like "class", "import", "const", or "export" triggers the block mechanism, heavily penalizing models that are legitimately describing actions or discussing topics without writing code.

For example, a phrase like: *"Let me update the class schedule for next week"* or *"We need to import all data from the database"* currently triggers a hallucination flag due to simple substring matching for `"class "` or `"import "`.

### Expected Behavior
The OutputValidator should only flag actual strings of code. Natural language use of programming keywords should not prematurely block execution.

### Proposed Solution
Implement a two-tier indicator mechanism in `OutputValidator._contains_code_indicators()`.
- **Strong indicators** (such as `<script`, `try:`, `async def`) remain unchanged and flag immediately.
- **Weak indicators** (such as `import `, `class `, `var `) will now require a line-anchor (e.g. `\nimport `) and must co-occur at least twice within a string segment to validate a positive match for code hallucination.
