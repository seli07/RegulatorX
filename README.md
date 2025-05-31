# RegulatorX
This is an agentic workflow for healthcare compliance.

![image](https://github.com/user-attachments/assets/639bcac6-08de-4de9-9961-b8b35a015f11)


RegulatorX is an advanced document processing and code mapping solution designed to maintain alignment between business requirements and software implementation. The system operates through several integrated components and processes.
Core Functionality: The platform accepts companion guides as input and systematically transforms them into structured Business Requirements Documents (BRDs) while establishing and maintaining direct mappings to the corresponding codebase elements.

### Processing Workflow: 
Upon initial document ingestion, the system converts the source material into markdown format to enhance structure and machine readability. The transformed document then undergoes BRD generation powered by Google's Gemini AI, which produces comprehensive documentation with uniquely identified requirements presented in structured tabular formats.

### Quality Assurance: 
The system implements an iterative improvement process that continuously enhances BRD quality through automated assessment. Each generated BRD is evaluated against the original companion guide using a quality scoring mechanism (0-1 scale), with refinements applied until the document achieves a quality threshold of 0.85 or reaches the maximum iteration limit.

### Change Management: 
The platform employs MD5 hash comparison algorithms to detect modifications in source companion guides. Upon change detection, the system performs differential analysis to identify specific alterations and subsequently maps these changes to relevant codebase components.

### Code Mapping Technology: 
A sophisticated Retrieval Augmented Generation (RAG) system maintains a comprehensive vector database of the entire codebase, enabling rapid identification of code segments requiring modification. The system generates precise modification recommendations, including target files, existing code segments, and proposed updates.

### Documentation and Tracking: 
The platform maintains comprehensive audit trails documenting all changes, improvements, and code mappings. This provides complete traceability of requirement evolution and corresponding code modifications over time.

## Architecture:
![image](https://github.com/user-attachments/assets/23cb6662-3cca-4cd9-b3c0-c12a1b5dd6de)

### Next steps:
1)	Implement end to end agentic verifications
2)	Integrate auth0 to signin to various models apis securely.   Currently , I define .env variable
3)	Implement finetuning workflow for human in the loop learning for introducing subject matter expertise
4)	Build UI for human input and interaction

