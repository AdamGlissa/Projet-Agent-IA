# Projet-Agent-IA

## Project Canvas

| # | Field | Your answer |
| :--- | :--- | :--- |
| 1 | Group name, members and private repository URL | **Group 6** : Mustapha Cheikh Abdellahi, Mohamed Glissa, Adam Tazi - 'https://github.com/AdamGlissa/Projet-Agent-IA' |
| 2 | Topic | **Literature review
crew** |
| 3 | Target user | Master/PhD students, R&D engineers, and researchers starting a new research topic or writing a state-of-the-art document. |
| 4 | Problem and current pain | Searching arXiv, filtering relevant papers, reading a lot of abstracts and PDFs then synthesizing a structured and cited state of the art takes a lot of time (days of fastidious manual work). |
| 5 | What the agent does, in 3 sentences | Given a research question and constraints (keywords, date range), the system queries the arXiv API, retrieves and indexes relevant open-access papers, and extracts key information. A multi-agent workflow drafts a structured state-of-the-art review with inline citations and improves it through a reflection loop checking coverage and source accuracy. Before exporting the final report, the user reviews and approves the selected corpus and the final draft. |
| 6 | Success criterion (metric and target) | **Citation faithfulness & coverage** (We can imagine testing the agent on at least 10 research queries using RAGAS faithfulness and answer relevancy scores alongside a quick human check, while making sure no citations are made up). | |
| 7 | Architecture: orchestration and agentic patterns | |
| 8 | Tools: name, input, output, one line each | - `search_arxiv(query, max_results)` -> `list[dict]`: queries the arXiv API and returns basic metadata (title, authors, year, abstract, PDF link).
- `index_and_retrieve_papers(paper_ids, question)` -> `list[str]`: chunks abstracts/texts into ChromaDB and returns the top-k passages for the query.
- `export_review_markdown(filename, content)` -> `str`: saves the final review and BibTeX entries to a Markdown file after human approval (HITL).
- Built-in `deepagents` tools: `write_todos` (task list), `write_file` / `read_file` (notes and drafts), `task` (sub-agents). |
| 9 | Data sources: access, size, licence, personal data | • **arXiv API & Open-Access papers**: public REST API (`export.arxiv.org`), ~10–30 papers per query (JSON/XML + PDF text), arXiv / Creative Commons open-access licences, no personal/confidential data.<br>• **Evaluation dataset**: 10+ research topics with expected key papers and reference criteria. |
| 10 | Human approval point: which action, who approves | **Action**: Exporting the final state-of-the-art report (`export_review_markdown`, and corpus validation before drafting). **Who**: The user via DeepAgents `interrupt_on` + `Command(resume=...)`. |
| 11 | LLM and stack choices, with any change from the defaults | |
| 12 | Top 3 risks and fallback plan | |
| 13 | Demo scenario for December 9, in 3 steps | |
