---
stepsCompleted: [1]
inputDocuments: ["README.md"]
session_topic: "RAG/AI Architecture for Milestone 4 - IT Agent System"
session_goals: "Explore technical architecture options and identify risks for RAG pipeline, vLLM integration, LangGraph orchestration, auto-index update mechanism, and HITL feedback loop"
selected_approach: ""
techniques_used: []
ideas_generated: []
context_file: "README.md"
communication_language: Vietnamese
document_language: English
---

# Brainstorming Session — RAG/AI Architecture (Milestone 4)

**Date:** 2026-03-19
**Project:** IT Agent System
**Facilitator:** Claude (BMAD Brainstorming)

---

## Session Overview

**Topic:** RAG/AI Architecture for Milestone 4 of the IT Agent System

**Goals:**
- Explore technical architecture options (RAG pipeline, vLLM integration, LangGraph orchestration)
- Design auto-index update mechanism (triggered by GLPI KB changes)
- Design HITL feedback loop
- Identify risks before implementation

**Out of Scope:** Agent Management UI, Milestone 5

### Context Guidance

From README.md — The system must:
1. Trigger when an IT ticket is created/updated in GLPI
2. Read ticket content → Search GLPI Knowledge Base via RAG
3. Post automated answer if confidence is high
4. Escalate to human agent if confidence is low or after 3 failed attempts
5. Run on self-hosted vLLM server (DeepSeek model)
6. Tech stack: Python | LangGraph | n8n | DeepSeek | RAG | GLPI

### Session Setup

_Brainstorming session initialized. Scope confirmed by user._

---

## Ideas & Exploration

_Content will be appended as brainstorming progresses._

