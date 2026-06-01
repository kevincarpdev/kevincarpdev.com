📌 Executive Summary & Context
The company operates at the intersection of wealth management, specialized HR/payroll, and healthcare.

Their core business model involves high-net-worth families or legal trusts funding home healthcare (e.g., a private nurse for a spouse). Instead of the family facing the massive legal risk of treating that nurse as an independent contractor or an informal cash employee, the company steps in as the legal employer of record via a W2 model. They handle the massive compliance headache—dealing with shifting state-by-state W2 laws, the new Department of Labor Overtime rules, and complex trust accounting—while providing a "single pane of glass" platform for their internal sales and operations teams.

🎯 High-Yield Interview Talking Points

1. The Domain & Business Logic (Trusts, Care, & Compliance)
   The Problem They Solve: A trust wants to legally pay for a spouse's home healthcare nurse using trust funds. If done improperly, it triggers massive tax, IRS, and labor law liabilities.

The Solution: The company acts as the W2 employer of record, taking on the burden of HR, payroll, and 50-state compliance.

The Compliance Moving Targets: Mention your awareness of how quickly this landscape shifts—specifically highlighting the new Overtime (OT) laws and constant state-by-state W2 tax code fluctuations. Emphasize your commitment to building systems that do things completely "by the book."

2. Operational Integration & Core Ecosystem
   The PEO & Payroll Engine: They leverage PrismHR (or a similar specialized SaaS geared toward Professional Employer Organizations) to handle outsourced HR, payroll processing, and issuing W2s to healthcare workers.

Financial & Resource Tracking: NetSuite serves as the heavy-duty back-office ERP to track trust disbursements, customer billing, and financial reporting.

The Internal Single Pane of Glass: They use Salesforce to drive internal sales and account management efficiency, pushing employee and client data into a unified view so internal teams aren't jumping between silos.

🛠️ Technical Alignment & Architecture
As an architect/developer, your job is to connect these disparate enterprise systems (Salesforce, NetSuite, PrismHR) into a seamless, high-performance, and secure product.

Modern Stack & Orchestration
Frontend: Next.js and TypeScript for a type-safe, lightning-fast, and modern user interface (for both internal staff and clients/trustees checking their balances).

Backend: Python for robust backend services, data processing, and handling complex business logic around payroll calculations and compliance rules.

Enterprise Integration: Utilizing Azure Logic Apps as the workflow orchestrator to reliably sync data between Salesforce, NetSuite, and the core database without breaking.

Engineering Velocity & Security Focus
CI/CD & AI Tooling: Leveraging GitHub Copilot Enterprise for accelerated development velocity, backed by Azure Pipelines for automated, reliable continuous integration and deployment.

Collaboration: Deeply familiar with running agile workflows using the Atlassian suite (Jira, Confluence).

The Security Opportunity: Acknowledge that with highly sensitive healthcare (HIPAA-adjacent) and financial trust data, code security is a critical area of focus. Position yourself as someone who can actively champion and implement improved security guardrails on the development side (e.g., automated SAST/DAST scanning in the pipeline, secure dependency management, and strict data maskings).

💬 Strategic Questions to Ask Them
"With Azure Logic Apps acting as the connective tissue between Salesforce, NetSuite, and PrismHR, what are the biggest bottlenecks your team currently faces regarding data synchronization or state-by-state compliance updates?"

"Given that you're handling trust funds across 50 states with shifting W2 and Overtime laws, how are you currently managing the business logic layers in the Python backend to keep the system agile yet perfectly 'by the book'?"

"You mentioned wanting to level up code security on the dev side. Are you looking to integrate automated security gates directly into your Azure Pipelines, or are you focusing more on developer training and secure coding practices with tools like Copilot Enterprise?"
