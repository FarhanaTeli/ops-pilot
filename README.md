# OpsPilot

OpsPilot is a portfolio project for agentic inventory and operations intelligence. It is designed to explore how an AI-assisted operations system can turn inventory data into useful observations, explanations, and recommendations while keeping the workflow understandable and auditable.

## Business Problem

Operations teams often work across spreadsheets, exports, and disconnected reporting tools. This makes it difficult to identify stock-out risk, excess inventory, slow-moving items, supplier issues, and changes in demand early enough to act. OpsPilot will provide a focused foundation for organizing operational data and building decision support around those questions.

## Planned Capabilities

- Ingest and validate inventory, sales, purchasing, and supplier data
- Track inventory levels, movement, reorder points, and stock-out risk
- Surface anomalies and operational trends
- Answer natural-language questions about operational data
- Explain the evidence behind findings and recommendations
- Support repeatable workflows through specialized agents
- Keep outputs traceable through logs, structured results, and tests

These capabilities are planned for later phases. Phase 1 contains project structure only.

## Planned Technology Stack

- Python for data processing, orchestration, and backend logic
- Pandas and Polars for tabular data workflows where appropriate
- SQLite initially, with a path to a production relational database
- SQL for transformations, validation, and operational analysis
- A lightweight API layer such as FastAPI when application services are introduced
- An LLM provider and agent orchestration framework added only when their use case is defined
- Pytest for automated tests
- Jupyter notebooks for exploratory analysis and documentation

Dependencies will be introduced incrementally as the corresponding capability is implemented.

## Data Approach

OpsPilot will use public, synthetic, or deliberately anonymized data. The project will not rely on private company data or commit sensitive operational information. Synthetic datasets may be generated to represent products, locations, suppliers, orders, inventory movements, and demand patterns. Public datasets will be documented with their source, license, and any preprocessing steps.

Raw and processed data locations are kept separate:

- `data/raw/` for original or source-shaped inputs
- `data/processed/` for validated and transformed outputs

Dataset files are ignored by default to reduce the risk of committing large or sensitive artifacts.

## Project Structure

```text
ops-pilot/
├── data/
│   ├── raw/
│   └── processed/
├── src/
├── sql/
├── tests/
├── docs/
├── notebooks/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Development Approach

OpsPilot will be built in small, verifiable phases. Each phase should introduce one clear capability, its supporting tests or documentation, and only the dependencies required for that capability. Agents and application code are intentionally deferred until the data and operational foundations are established.
