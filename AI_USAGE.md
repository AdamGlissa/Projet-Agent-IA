# AI Usage Declaration

## 1. Tools Used
- **Chat LLM:** Claude - Opus 5.5
- **Code Editor:** Claude Code in the terminal

---

## 2. Approach by Phase
- **Design & Scoping (EDT1):** Used AI to explore multi-agent vs. `deepagents` trade-offs and clarify architecture choices.
- **Code:** We designed the initial architecture ourselves based on our prior experience with deepagents and the TPs, then asked Claude to implement the code since it's only the beginning and we asked him to code step by step so we could review each stage and make sure we fully understood everything.
- **Debugging:** Not done yet
- **Evaluation:** Note done yet

---

## 3. Key Prompts (EDT1)

1. **Prompt comparing `deepagents` vs. CrewAI for literature review:**
   - *Summary of answer:* Highlighted the trade-offs between CrewAI and `deepagents` (built on LangChain/LangGraph), confirming that `deepagents` fits our workflow via task planning (`write_todos`), working files (`write_file`/`read_file`), and sub-agents (`task`) while remaining feasible locally with Ollama.
2. **Prompt reviewing our Project Canvas wording and simplifying technical phrasing:**
   - *Summary of answer:* Checked the consistency of our drafted Project Canvas fields (`README.md`) against the session guidelines and suggested clearer wording (e.g., replacing *"factual grounding"* with *"source accuracy"* in Field 5).
3. **Prompt clarifying RAGAS metrics (`faithfulness` and `answer relevancy`) and HITL gating:**
   - *Summary of answer:* Explained how `faithfulness` checks claims against retrieved passages, how `answer relevancy` checks alignment with the initial query, and how `interrupt_on` / `Command(resume=...)` pauses execution before final Markdown export.
4. **Prompt asking Claude to implement our initial `deepagents` skeleton step by step:**
   - *Summary of answer:* Generated the modular boilerplate for our self-designed architecture stage by stage so we could inspect, test, and verify our understanding of each component.

---

## 4. Kept, Changed, or Rejected
- **Kept:** Using `qwen2.5:7b` via local Ollama, `nomic-embed-text` + persistent ChromaDB, bounded reflection (`max_revisions = 2`), and HITL approval before `export_review_markdown`.
- **Changed:** The AI initially suggested CrewAI because it was mentioned in the project reference material, but we chose `deepagents` ourselves because we were already familiar with it and found it better suited to our workflow. 
- **Rejected:** We rejected downloading and indexing full PDFs for every paper by default in the first pass (preferring abstracts and open-access text selectively via `index_and_retrieve_papers` to keep local latency and chunk noise reasonable).
- **How we verified:** Reviewed every canvas field against the project requirements (target user, accessible non-confidential data, non-retrieval tool, local feasibility, measurable success criterion, HITL action).

---
 
## 5. Original Contributions
- **Topic selection & problem framing:** Chose Topic #4 (*Literature review crew*) and defined the target user, core pain points, the 3-step demo scenario...
- **Success criteria & evaluation metrics:** Defined our own measurable success criteria (targeting ≥ 85% citation faithfulness and answer relevancy with RAGAS + a manual checklist over 10+ queries and 0 fabricated citations) to match realistic academic and hardware constraints.
- **Architecture, stack & HITL boundaries:** Decided to use `deepagents` (based on our prior experience rather than the suggested CrewAI option), scoped the 3 core tools (`search_arxiv`, `index_and_retrieve_papers`, `export_review_markdown`), and placed the human approval gate specifically on corpus confirmation and final Markdown export.

---
 
## 6. Individual Contributions (EDT1)
Overall, since this was the start of the project, we all discussed and thought through the project and the choices we wanted to make together.

- **Adam Tazi:** Took charge of drafting the Project Canvas in `README.md` and worked through the questions related to data sources and success criteria (`[commit hash / link]`).
- **Mustapha Cheikh Abdullahi:** Also contributed to drafting the Project Canvas and focused more specifically on tool selection and architecture choices (`[commit hash / link]`).
- **Mohamed Glissa:** Investigated whether `deepagents` or CrewAI was the better fit for the project and started coding a simple initial architecture (`[commit hash / link]`).
