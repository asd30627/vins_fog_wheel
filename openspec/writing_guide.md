# Writing Guide & Style Standards

This document establishes the copywriting, formatting, and structural standards for the repository's documentation. Both human authors and AI agents must follow these rules.

---

## ✍️ Language & Tone

- **Voice**: Use active voice instead of passive voice whenever possible (e.g., "The server rejects the request" instead of "The request is rejected by the server").
- **Language**: 所有文件內容與 AI 協作回覆預設使用繁體中文。此規則適用於現有的 explore → propose → apply → archive workflow；不要為了語言要求新增其他 workflow、skill 或文件。
- **必要英文保留**: 技術名詞、程式識別字、命令、檔案路徑、數學符號、論文名稱與引用可保留英文。首次出現且可能造成理解困難的技術名詞，應附上簡短中文說明。
- **Term Consistency**: Use exact terms defined in the glossary. Do not coin new acronyms or abbreviations without listing them.
- **Clarity & Conciseness**: Keep paragraphs under 5 lines. Use bulleted lists for complex rules or conditions.

---

## 🤖 AI Writing Discipline (agent-facing)

The following rules govern all AI-generated text in this project. They apply during every workflow phase (explore, propose, apply, archive).

**Sentence-level rules:**
- **Lead with the payload**. First sentence of every paragraph = the fact, the rule, or the decision. No preamble.
- **No throat-clearing**. Never open with: "It is worth noting", "Furthermore", "Moreover", "In this section we will discuss", "It is important to emphasize", "Delving into", "As previously mentioned".
- **One idea per paragraph**. If a paragraph exceeds 4 sentences, split it.
- **Active voice**. "The system processes the data" — not "The data is processed by the system".

**Structure-level rules:**
- **Inverted Pyramid**: The most critical conclusion or rule MUST be the first sentence of the section. Edge cases, background context, and exceptions must follow, never precede.
- Prefer tables over bullet lists when comparing ≥3 items across ≥2 dimensions.
- Prefer bullet points over paragraphs for enumerating rules or constraints.
- **No recaps**. Never summarize what you just wrote at the end of a section. The reader can scroll up.
- **No previews**. Never preview what comes next ("In the following section, we will..."). Use headings.

**Phase-specific rules:**
- **Explore phase**: Output decisions, boundaries, and structural skeletons only. Do not produce publication-ready prose. See `conventions.md` for Depth Ceiling rules.
- **Apply phase**: This is where prose gets written. Expand explore-notes decisions into polished, human-readable documentation.

---

## 🎨 Markdown Formatting Standards

- **Header Hierarchy**: Maintain a strict sequence. Do not skip header levels (e.g., do not follow `#` with `###`).
- **Lists**: Wrap lists with empty lines before and after. Use `-` for unordered lists and `1.` for ordered procedures.
- **Code Blocks**: Always specify the language for syntax highlighting (e.g., ````markdown` or ````yaml`).
- **Tables**: Use standard GitHub Flavored Markdown (GFM) tables. Always add a header row.

---

## 📐 Diagrams & Visuals

- **ASCII Diagrams**: Use text-based ASCII art for system architecture, state machines, and data flows.
- **ASCII Art Rules**:
  - Keep widths within 80 characters to prevent wrapping.
  - Use box-drawing characters (`┌`, `─`, `┐`, `│`, `└`, `┘`, `├`, `┤`, `┼`) rather than hyphens and pipes for cleaner rendering.
- **Image Referencing**: Save images in `docs/images/` and use relative markdown syntax `![caption](../docs/images/file.png)`.

---

## 📖 Glossary & Terminology

Align all naming and concepts with this single source of truth.

| Term | Abbreviation | Definition | Matches Symbol |
|---|---|---|---|
| [Example: Main API Server] | MAS | Central system for managing API requests | `Main_Server` |

---

## 📋 Copywriting & Proofreading Checklist

Before submitting a change or archiving, the Agent must verify:
- [ ] No grammar mistakes or placeholder TODOs left in the final document.
- [ ] All terms match the Glossary exactly.
- [ ] Header levels follow conventions strictly.
- [ ] ASCII art fits within 80-character width and renders cleanly.
