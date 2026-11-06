# **EVORA: AI-Assisted Multimodal Forensic Evidence Fusion and Investigation Support System**

## **1\. Introduction**

EVORA is an AI-assisted forensic investigation support system developed to assist investigators in analyzing, connecting, prioritizing, and interpreting heterogeneous digital and multimedia evidence within a unified environment. Modern forensic investigations can involve a wide variety of evidence, including CCTV recordings, photographs, documents, mobile-device logs, network records, transaction information, GPS traces, communication records, and other digital artifacts. These sources are generally generated in different formats and may contain different identifiers, timestamp representations, locations, and levels of reliability. When such evidence is examined independently, relationships between different sources can remain difficult to identify and investigators may need to manually inspect a large volume of information.

EVORA addresses this challenge by providing a unified framework in which evidence can be collected, integrity information can be recorded, processed, normalized, correlated, prioritized, represented, analyzed, explained, and reviewed by an investigator. A major feature of the proposed system is an Adaptive Evidence Triage System that helps determine which evidence should receive investigative attention first. The triage mechanism considers factors such as evidence relevance, relationships with known case entities, graph connectivity, temporal proximity, corroboration, evidence gaps, conflicts, and source-quality information. As new information is discovered, the system can update the priority of remaining evidence, creating an iterative triage-analysis-retriage workflow.

The system is designed as an investigation-support tool rather than an autonomous decision-making system. Its findings remain subject to human verification and are not intended to determine guilt, establish criminal responsibility, or replace professional forensic judgment.

## **2\. Problem Statement**

The major problem addressed by EVORA is the difficulty of correlating and prioritizing heterogeneous forensic evidence obtained from multiple independent sources. A single investigation may contain visual evidence from CCTV, textual information from documents, technical information from device and network logs, financial information from transaction records, and spatial information from GPS data. Each source can provide valuable information, but examining them separately can require significant manual effort and may make cross-source relationships difficult to discover.

Another challenge is determining which evidence should be examined first. Investigators may receive hundreds or thousands of files, but not every item has the same relevance to the current investigation. Evidence connected to important entities, multiple independent sources, unusual patterns, evidence conflicts, or unexplained information gaps may deserve earlier examination. Therefore, there is a research opportunity to investigate a lightweight architecture that combines multimodal evidence extraction, common representation, graph-based reasoning, adaptive evidence triage, uncertainty handling, explainability, provenance, and human verification within one experimental workflow.

## **3\. Proposed Solution**

EVORA proposes an integrated evidence-fusion architecture in which heterogeneous forensic artifacts are transformed into a common representation of entities, events, relationships, observations, and evidence sources. The system uses artificial intelligence and data-processing techniques appropriate to different evidence modalities and subsequently combines their outputs for cross-source analysis.

The extracted information is represented using entities, events, timestamps where available, locations, relationships, confidence information, source information, and provenance. These elements are used to construct a forensic knowledge graph and support cross-source relationship analysis.

A dedicated Evidence Triage System analyzes the available evidence and assigns investigative priority based on multiple factors. These can include relevance to known case entities, number of graph connections, temporal proximity to important observations, corroboration by independent sources, relationship to detected conflicts or evidence gaps, and source-quality information.

After initial evidence is analyzed, newly discovered entities and relationships can modify the priorities of other evidence. This creates an adaptive investigation cycle in which the system can repeatedly prioritize remaining evidence based on the latest available information.

Additional analytical components examine relationships, unusual patterns, potential inconsistencies, evidence gaps, and uncertainty. An explainable AI layer provides reasons for important findings and triage decisions, while an evidence-grounded retrieval system allows investigators to interact with the collected case information using natural-language queries.

## **4\. Evidence Acquisition and Intake**

The workflow begins with an evidence-intake module. An investigator creates a case and uploads the available digital or multimedia evidence. The system may accept CCTV recordings, images, documents, mobile-device logs, network logs, transaction records, GPS information, messages, and other structured or unstructured files.

Each evidence item receives a unique Evidence ID that allows it to be referenced throughout the investigation. Relevant metadata, including evidence type, source, filename, acquisition information, processing status, available timestamps, and other available metadata, can also be maintained.

The Evidence ID becomes the primary reference used throughout the system. When an analytical result is produced, the system can associate the result with the Evidence IDs that contributed to it. This allows investigators to trace analytical findings back to their original sources.

## **5\. Evidence Integrity and Provenance**

Before analytical processing, EVORA can generate a cryptographic hash for each evidence artifact. A hash provides a way to associate subsequent processing activities with the original digital artifact.

The system maintains information about the evidence source and the operations performed on it. Provenance information can subsequently be associated with extracted entities, events, relationships, analytical results, triage decisions, and investigator decisions.

When AI-based processing is performed, information such as the model used, model version, processing parameters, input evidence, output, and processing time can also be recorded. For generative AI operations, the system can additionally maintain information such as the model version, prompt template, retrieved evidence identifiers, generated response, and verification status.

This creates a traceable history of how information moves through the analytical pipeline.

## **6\. Multimodal Evidence Processing**

After evidence intake, EVORA applies different processing techniques depending on the nature of the evidence.

CCTV recordings and images can be analyzed using computer-vision techniques to identify persons, vehicles, objects, or other relevant visual information. Optical character recognition can extract text from scanned documents or images.

Natural-language-processing techniques can process documents, reports, messages, and other textual records to identify relevant entities such as people, organizations, locations, dates, phone numbers, account identifiers, and device identifiers.

Structured mobile and network logs can be processed to identify devices, IP addresses, connection events, authentication activities, and system operations.

Transaction records can provide information about accounts, transaction identifiers, amounts, merchants, and available timestamps.

GPS records can contribute information about locations and movement observations.

The purpose of multimodal processing is to convert heterogeneous raw evidence into structured information that can be compared and correlated across sources.

## **7\. Entity and Event Extraction**

The information extracted from different evidence sources is converted into meaningful entities and events.

Entities may include:

* Persons
* Devices
* Vehicles
* Accounts
* IP addresses
* Locations
* Organizations
* Files
* Phone numbers
* Other investigation-relevant objects

Events may include:

* Person detected in an image or video
* Vehicle detected
* Device connected to a network
* Login performed
* Message sent
* Transaction performed
* Device associated with a location
* File created or modified
* Network connection established
* Account activity observed

Each extracted entity or event retains a connection to its source evidence so that investigators can determine where the information originated.

## **8\. Common Evidence Representation**

A normalization layer converts information from different evidence sources into a common structure. Different evidence sources can represent dates, times, locations, identifiers, and events in different ways. EVORA attempts to standardize these representations so that information originating from different modalities can be compared.

The common representation contains elements such as:

* Entity
* Event
* Timestamp where available
* Location
* Relationship
* Source
* Confidence
* Evidence ID
* Provenance
* Processing information

This provides an interoperability layer between heterogeneous evidence sources and allows the analytical components to operate on a consistent representation.

The common representation is particularly important for the Evidence Triage System because it allows evidence from different modalities to be evaluated using comparable factors.

## **9\. Forensic Knowledge Graph**

The normalized evidence is represented through a forensic knowledge graph. The graph contains entities, events, evidence items, and relationships between them.

For example, a person can be associated with a device, the device can be associated with an IP address, and the IP address can be associated with a network event. Similarly, a vehicle detected in CCTV footage can be associated with a particular location and an available timestamp.

Relationships within the graph can retain references to the evidence that supports them.

For example:

Person P01 → used → Device D01

Device D01 → connected\_to → IP 192.168.X.X

Vehicle V03 → observed\_at → Location L02

Transaction T01 → associated\_with → Account A07

Each relationship can retain supporting Evidence IDs and relevant confidence or source information.

The graph therefore serves both as a representation of relationships and as an analytical source for the Evidence Triage System.

## **10\. Cross-Source Relationship Analysis**

The knowledge graph enables EVORA to search for relationships across different evidence sources.

Connections may be identified through:

* Common identifiers
* Shared devices
* Shared accounts
* Shared IP addresses
* Shared locations
* Related vehicles
* Related persons
* Repeated observations
* Available temporal proximity
* Multiple independent sources

For example, if a device appears in a network record and the same device identifier is associated with another evidence source, the system can identify the observations as potentially related.

Such relationships are presented as investigative findings rather than automatic conclusions and remain subject to human verification.

## **11\. Adaptive Evidence Triage System**

The Adaptive Evidence Triage System is a major component of EVORA. Its purpose is to help investigators determine which available evidence should receive attention first.

Instead of treating all evidence items equally, the system evaluates each item using multiple factors, including:

* Investigation relevance
* Relationship with known case entities
* Knowledge-graph connectivity
* Corroboration from independent evidence
* Available temporal proximity
* Relationship to evidence gaps
* Relationship to detected conflicts
* Source-quality information
* Extraction confidence
* Number of supporting observations

The system then assigns an investigative priority to the evidence.

A simplified priority classification may be:

* Priority 1 – High investigative priority
* Priority 2 – Moderate-high priority
* Priority 3 – Moderate priority
* Priority 4 – Lower current priority

The priority is not a judgment of whether evidence is true, false, incriminating, or exonerating. It only indicates how useful the evidence may be for the next stage of investigation based on the currently available information.

## **12\. Triage Scoring**

The triage system can calculate a prototype priority score using weighted factors.

For example:

Triage Score \=

0.25 × Relevance

* 0.20 × Connectivity
* 0.15 × Corroboration
* 0.15 × Gap Relevance
* 0.10 × Source Quality
* 0.10 × Conflict Relevance
* 0.05 × Temporal Proximity

The exact weights can be treated as experimental parameters and adjusted during evaluation.

The resulting score can then be converted into priority levels.

For example:

80–100 → Priority 1

60–79 → Priority 2

40–59 → Priority 3

0–39 → Priority 4

These values are prototype design choices rather than established forensic standards. The evaluation should examine how different weighting strategies affect evidence prioritization.

## **13\. Evidence Relevance Analysis**

The system evaluates how strongly an evidence item is connected to the current investigation.

For example, if the investigation already contains known entities such as:

Person P01

Device D01

Vehicle V03

Location L02

Account A07

then an evidence item containing several of these entities can receive a higher relevance component.

An unrelated document containing none of the known entities may receive a lower relevance component.

The system should display the basis of the relevance assessment rather than simply presenting a numerical value.

## **14\. Evidence Connectivity Analysis**

Knowledge-graph connectivity can be used as one factor in triage.

For example:

CCTV\_023 may be connected to:

* Person P01
* Vehicle V03
* Location L02
* Device D01
* Evidence E17
* Evidence E21

This indicates that the evidence is connected to several other observations in the case.

Another evidence item may have only one weak relationship.

The triage engine can therefore use the number and type of meaningful connections as one factor in determining investigative priority.

Connectivity does not establish that an entity is responsible for an event. It only identifies relationships requiring examination.

## **15\. Evidence Corroboration Analysis**

EVORA can examine whether information from one evidence item is supported by independent evidence sources.

For example:

CCTV → Person P01

GPS → Location L02

Mobile Log → Device D01

Network Log → Device D01

If multiple independent sources provide related observations, the corresponding evidence cluster can receive increased investigative priority.

The system should describe this as corroborating observations rather than treating multiple sources as automatic proof of a conclusion.

## **16\. Evidence Conflict Analysis**

The system can identify evidence items that appear to contain conflicting observations.

For example:

CCTV\_27:

Person P01 detected at Location A.

GPS\_11:

Associated device observed at Location B during an overlapping period.

Instead of declaring one source false, EVORA marks the situation as a potential conflict requiring examination.

Potential explanations may include:

* Device-clock differences
* Time-zone differences
* Recording delays
* Metadata errors
* Location inaccuracies
* Device-user mismatch
* Genuine movement
* Other contextual explanations

Evidence contributing to an important unresolved conflict can receive increased triage priority because it may help clarify the situation.

## **17\. Evidence Gap Detection**

EVORA can identify areas where available evidence is incomplete or insufficient.

An evidence gap does not mean that an event did not occur. It indicates that the available evidence does not currently provide sufficient information for a particular part of the investigation.

For example, the system may identify:

Evidence gap:

21:30–21:45

Available evidence:

CCTV\_01 → before interval

GPS\_04 → after interval

Mobile\_07 → no record during interval

The system can then identify available evidence sources that may potentially provide information relevant to the gap, such as additional CCTV files, mobile logs, network records, GPS records, or transaction data.

Evidence items related to an important gap can receive increased triage priority.

This feature is therefore connected directly to the adaptive triage mechanism.

## **18\. Evidence Cluster Prioritization**

EVORA can prioritize groups of connected evidence instead of treating every file independently.

For example:

CCTV\_12

↓

Person P01

↓

Device D01

↙ ↘

GPS\_07 Mobile\_03

↓

Transaction\_09

These items form a connected evidence cluster.

The system can identify the cluster and present:

Evidence Cluster 04

Number of connected items: 5

Known entities: P01, D01, Account A07

Supporting sources: CCTV, GPS, Mobile, Transaction

The investigator can then examine the complete cluster rather than manually searching for every relationship.

## **19\. Adaptive Re-Triage**

Adaptive re-triage is one of the central concepts of EVORA.

Initial triage is performed immediately after evidence processing. However, investigation does not remain static. When an investigator examines high-priority evidence, the system may discover new entities, relationships, conflicts, or evidence gaps.

These new observations can change the priority of remaining evidence.

For example:

Initial evidence:

500 items

Initial priority:

CCTV\_023 → Priority 1

GPS\_017 → Priority 2

Mobile\_009 → Priority 3

After CCTV\_023 is analyzed, the system discovers:

Person P01

Device D01

Vehicle V03

Location L02

The system then examines the remaining evidence and discovers that GPS\_017 and Mobile\_009 are connected to these newly identified entities.

The priorities can therefore change:

GPS\_017 → Priority 1

Mobile\_009 → Priority 1

Network\_031 → Priority 2

This creates the following investigation loop:

Evidence Intake

↓

Initial Triage

↓

Evidence Analysis

↓

New Information

↓

Relationship / Conflict / Gap Detection

↓

Re-Triage

↓

Further Evidence Analysis

↓

Human Verification

This adaptive loop is a major research component of EVORA.

## **20\. "Why Was This Evidence Prioritized?" Explanation**

Every important triage decision should be accompanied by an explanation.

For example:

Evidence: CCTV\_023.mp4

Priority: High

Reasons:

* Contains known case entity Person P01
* Connected to six other evidence items
* Contains Vehicle V03
* Associated with an investigation-relevant location
* Corroborated by GPS\_017
* Related to an identified evidence gap
* Associated with a potential conflict requiring verification

Potential issue:

Timestamp differs from a related mobile record.

Recommended review:

Compare CCTV\_023 with GPS\_017 and Mobile\_009.

This feature ensures that the investigator does not receive an unexplained priority ranking.

## **21\. Anomaly Detection**

An anomaly-analysis component examines structured evidence for unusual patterns.

Machine-learning techniques such as Isolation Forest and DBSCAN, together with statistical and rule-based approaches, can be applied to identify unusual:

* Device activity
* Location patterns
* Login sequences
* Transaction behavior
* Network activity
* Event frequencies

An anomaly represents an observation that differs from an expected pattern and can therefore be useful for investigation prioritization.

However, the system does not equate an anomaly with criminal behavior. Unusual activity may have legitimate explanations, and automated anomaly detection can generate false positives.

Detected anomalies can become additional inputs to the Evidence Triage System.

## **22\. Evidence Reliability and Uncertainty**

EVORA incorporates evidence reliability and uncertainty into its analytical representation.

Evidence obtained from different sources may have different:

* Extraction confidence
* Source quality
* Levels of corroboration
* Metadata completeness
* Temporal consistency
* Potential contradictions

Instead of presenting every finding as equally certain, the system can maintain information about observations supporting a finding, contradictory observations, extraction confidence, and the number of independent sources providing related information.

This allows investigators to understand both the detected relationship and the available evidence supporting it.

Uncertainty can also be displayed as part of the triage explanation.

## **23\. Alternative Hypothesis Analysis**

The system also supports alternative-hypothesis reasoning.

Rather than generating a single interpretation of a case, EVORA can organize different plausible explanations based on the available evidence.

For example, if a particular device is associated with a person, one possible explanation may be:

Hypothesis A:

Person P01 operated Device D01.

Another possibility may be:

Hypothesis B:

Device D01 was used by another individual.

The system can organize:

* Supporting evidence
* Contradictory evidence
* Missing information
* Evidence requiring verification

for each hypothesis.

This approach is intended to support structured investigation rather than generate an unsupported automated narrative.

## **24\. Explainable Artificial Intelligence**

Explainability is incorporated into EVORA so that important analytical findings and prioritization decisions are accompanied by understandable reasons.

A relationship identified by the knowledge graph may be explained through:

* Shared identifiers
* Common devices
* Common locations
* Available temporal proximity
* Repeated observations
* Independent corroboration

Where machine-learning models are used, techniques such as SHAP and feature-importance analysis can provide additional explanations.

Counterfactual analysis can also be used to examine which conditions influence an analytical result.

For example:

"If the shared device identifier were removed, this relationship would no longer satisfy the selected relationship criteria."

The purpose of explainability is to allow investigators to inspect why a relationship, anomaly, or triage priority was produced rather than receiving only an unexplained output.

## **25\. Evidence-Grounded RAG**

EVORA can incorporate a Retrieval-Augmented Generation component that allows investigators to query case information using natural language.

An investigator could ask:

"Which evidence connects Device D01 and Person P01?"

or:

"Show the evidence associated with Vehicle V03."

or:

"Why was CCTV\_023 given high priority?"

The retrieval component first searches structured evidence, the knowledge graph, extracted entities and events, triage information, and associated metadata.

The language model then generates a response based on the retrieved information.

The response should include relevant Evidence IDs whenever possible so that the investigator can trace the answer back to its supporting records.

This design aims to reduce unsupported generation by grounding responses in the evidence available within the case.

## **26\. Evidence-Based Natural-Language Investigation**

The natural-language interface provides an accessible way for investigators to interact with complex case information.

Rather than manually searching multiple datasets, an investigator can formulate questions about:

* Entities
* Evidence
* Relationships
* Devices
* Accounts
* Locations
* Anomalies
* Evidence gaps
* Conflicts
* Triage priorities

For example:

"Why is Mobile\_009 high priority?"

"What evidence connects P01 with D01?"

"Which evidence items are related to the detected conflict?"

"Which evidence belongs to the same connected cluster?"

The retrieved answer can include references to relevant Evidence IDs.

The language model therefore acts primarily as an interface for evidence retrieval and summarization rather than as an autonomous forensic decision-maker.

## **27\. Investigator Dashboard**

The outputs of the different analytical modules are presented through an investigator-oriented dashboard.

The dashboard can contain:

### **Case Overview**

* Case ID
* Evidence count
* Evidence types
* Processing status

### **Evidence Triage**

* Priority 1 evidence
* Priority 2 evidence
* Priority 3 evidence
* Priority 4 evidence
* Evidence clusters
* Triage explanations

### **Knowledge Graph**

* Entities
* Relationships
* Supporting Evidence IDs

### **Relationship Analysis**

* Cross-source connections
* Shared entities
* Related evidence

### **Anomaly Analysis**

* Detected anomalies
* Supporting observations
* Anomaly explanations

### **Conflict Analysis**

* Potentially conflicting observations
* Evidence involved
* Possible explanations

### **Evidence Gap Analysis**

* Areas with insufficient evidence
* Related evidence sources
* Suggested evidence for examination

### **Reliability and Uncertainty**

* Source quality
* Extraction confidence
* Corroboration
* Contradictions

### **Alternative Hypotheses**

* Hypothesis
* Supporting evidence
* Contradicting evidence
* Missing information

### **Natural-Language Investigation**

* Investigator questions
* Retrieved evidence
* Evidence-grounded answers

The dashboard should allow investigators to move from a high-level finding directly to the supporting evidence.

## **28\. Human Verification**

Human verification is an essential part of the EVORA workflow.

System-generated findings can be reviewed by the investigator and categorized as:

* Accepted
* Rejected
* Needs Investigation

For triage decisions, the investigator can also manually adjust priority when appropriate.

The system can record the investigator's decision as part of the audit trail.

EVORA does not determine guilt, establish criminal responsibility, or replace professional forensic judgment.

Instead, it provides analytical support that helps investigators:

* Discover relationships
* Prioritize evidence
* Examine unusual patterns
* Identify conflicts
* Identify evidence gaps
* Compare alternative explanations
* Review supporting evidence

Human review therefore remains part of the final investigative process.

## **29\. Audit and Provenance Management**

EVORA maintains an audit layer that records important activities performed during the investigation.

The audit log can include:

* Evidence ingestion
* Evidence hash generation
* Source recording
* Entity extraction
* Event extraction
* Data normalization
* Knowledge-graph construction
* Relationship analysis
* Triage calculation
* Re-triage calculation
* Anomaly detection
* Conflict detection
* Evidence-gap detection
* Explanation generation
* RAG retrieval
* AI-generated responses
* Investigator decisions
* Manual priority changes

For generative AI operations, additional information such as model version, prompt template, retrieved evidence identifiers, processing parameters, generated response, timestamp, and verification status can be maintained.

This creates a traceable record of how an analytical result or triage decision was produced.

## **30\. Technology Requirements**

The proposed prototype can be implemented primarily using Python.

Pandas and NumPy can be used for structured data processing.

OpenCV and pretrained YOLO models can support image and video analysis.

OCR tools can extract text from visual documents.

spaCy or transformer-based NLP models can support entity and event extraction.

Scikit-learn can provide machine-learning algorithms and anomaly-detection methods.

Neo4j and Cypher can be used for knowledge-graph storage and querying.

SHAP can support selected explainability tasks.

Streamlit can be used to create the investigator dashboard.

Plotly and graph-visualization libraries can display relationships and analytical results.

SQLite or PostgreSQL can maintain application and case metadata.

A vector database or embedding-based retrieval layer can be used for evidence-grounded RAG if required.

## **31\. Dataset and Experimental Environment**

The initial implementation can use synthetic or publicly available datasets rather than real investigative records.

Synthetic cases can be created to contain:

* Related evidence
* Unrelated evidence
* Shared entities
* Missing information
* Conflicting observations
* Noisy records
* False or weak associations
* Multiple evidence sources supporting the same observation

For the Evidence Triage System, the synthetic dataset should also contain predefined relationships and known evidence priorities so that the prioritization mechanism can be evaluated.

Multiple synthetic cases can be generated to test whether the system consistently identifies relevant evidence and whether the adaptive re-triage mechanism changes priorities appropriately when new information becomes available.

## **32\. Evaluation**

The performance of EVORA can be evaluated using several complementary metrics.

### **Entity and Event Extraction**

Precision, recall, and F1-score can be used when labeled data is available.

### **Relationship Detection**

Known relationships can be compared against detected relationships.

Evaluation can include:

* True relationships identified
* False associations
* Precision
* Recall
* F1-score

### **Evidence Triage**

The triage system can be evaluated using synthetic cases with predefined relevant evidence.

Possible metrics include:

* Top-k relevant evidence recall
* Precision at k
* Mean reciprocal rank
* Priority consistency
* Ranking changes after new evidence
* Time or number of items required to reach relevant evidence

The adaptive component can specifically evaluate whether newly discovered information causes logically appropriate changes in evidence priority.

### **Evidence-Gap Detection**

Deliberately introduced missing evidence can be used to evaluate whether the system identifies the expected gaps.

### **Conflict Detection**

Known conflicting observations can be introduced into synthetic cases and the system can be evaluated based on whether those conflicts are correctly identified.

### **Anomaly Detection**

Synthetic unusual patterns can be introduced to measure anomaly detection performance and false-positive behavior.

### **Explainability**

Explanations can be evaluated by checking whether the stated reasons correspond correctly to the evidence and features that actually contributed to the finding or triage decision.

### **RAG Evaluation**

The evidence-grounded RAG component can be evaluated using:

* Evidence-reference correctness
* Retrieval accuracy
* Response grounding
* Unsupported statement rate
* Correct Evidence ID references

## **33\. Comparison with Existing Systems**

Existing forensic applications already provide significant capabilities related to digital evidence analysis, relationship discovery, multimedia investigation, and evidence prioritization.

Cellebrite Pathfinder provides multi-device analytics, link analysis, timelines, AI-assisted media analysis, and investigative capabilities.

Magnet AXIOM provides evidence recovery and analysis across multiple sources together with Connections and Timeline capabilities.

Autopsy provides broad digital-forensic examination capabilities and timeline-based analysis across different artifact categories.

Maltego provides strong graph-based link analysis and integration with multiple information sources.

Therefore, EVORA should not be positioned as a replacement for these established platforms or as the first system to combine AI, graphs, relationships, or evidence prioritization.

Its proposed distinction is the explicit integration of an adaptive evidence-triage mechanism with heterogeneous evidence extraction, common entity-event representation, provenance, graph-based relationship analysis, evidence-gap analysis, conflict analysis, uncertainty representation, alternative hypotheses, explainable AI, evidence-grounded retrieval, and human verification within a lightweight and reproducible academic architecture.

## **34\. Comparative Uniqueness of EVORA**

The major difference between EVORA and existing systems is the proposed investigation feedback loop.

Traditional evidence analysis can be represented as:

Evidence → Analysis → Results

EVORA proposes:

Evidence → Initial Triage → Analysis → New Relationships / Gaps / Conflicts → Re-Triage → Further Analysis → Explanation → Human Verification

This makes evidence prioritization an active part of the investigation rather than merely a filtering mechanism.

The system can use information discovered during analysis to determine which remaining evidence may deserve additional attention.

The following characteristics form the main research identity of EVORA:

1. Adaptive Evidence Triage
2. Evidence Re-Triage based on newly discovered information
3. Knowledge-graph-driven evidence prioritization
4. Evidence cluster prioritization
5. Evidence-gap-based prioritization
6. Conflict-aware prioritization
7. Explainable triage decisions
8. Reliability and uncertainty representation
9. Alternative hypothesis analysis
10. Evidence-grounded natural-language investigation
11. Explicit provenance and AI audit logging
12. Human verification

## **35\. Proposed Research Contribution**

The principal research contribution of EVORA is the design and evaluation of a unified evidence-fusion architecture for heterogeneous forensic information with an adaptive evidence-prioritization mechanism.

Instead of concentrating on a single forensic modality or a single analytical task, the proposed architecture connects multiple evidence sources through a common entity-event representation.

The resulting representation supports graph-based relationship reasoning and evidence prioritization.

The system further incorporates:

* Evidence triage
* Adaptive re-triage
* Evidence clusters
* Evidence-gap analysis
* Conflict detection
* Anomaly detection
* Uncertainty representation
* Alternative hypotheses
* Explainability
* Provenance
* Evidence-grounded natural-language interaction
* Human verification

The proposed research therefore investigates whether a transparent, evidence-grounded triage-and-analysis workflow can help investigators identify relevant evidence more efficiently while maintaining traceability and human control.

## **36\. Uniqueness of the Proposed System**

The originality of EVORA should be considered primarily at the level of its architecture and methodology rather than at the level of individual technologies.

Computer vision, NLP, knowledge graphs, anomaly detection, evidence triage, explainable AI, and retrieval-augmented generation are established technologies.

The proposed research direction combines these components around an adaptive forensic evidence-fusion workflow.

The central idea is that evidence prioritization should not remain static. Instead, the system can update the priority of remaining evidence whenever new entities, relationships, conflicts, anomalies, or evidence gaps are discovered.

Each important prioritization decision is linked to its contributing evidence and accompanied by an explanation.

The system also represents uncertainty and maintains provenance so that investigators can trace analytical findings back to their sources.

This combination provides the basis for investigating a transparent, auditable, and adaptive forensic AI architecture.

## **37\. Research Scope**

EVORA is intended as a research prototype that can demonstrate the feasibility of AI-assisted evidence fusion and adaptive evidence prioritization within an academic development period.

The project can focus on structured and semi-structured evidence rather than attempting complete forensic acquisition from physical devices.

It can use pretrained AI models instead of training large models from scratch and can rely on synthetic or public datasets for experimentation.

The core implementation can prioritize:

* Evidence intake
* Evidence hashing
* Multimodal extraction
* Entity and event extraction
* Common evidence representation
* Knowledge graph
* Relationship analysis
* Adaptive Evidence Triage
* Evidence cluster analysis
* Evidence-gap detection
* Conflict detection
* Anomaly detection
* Reliability and uncertainty
* Alternative hypotheses
* Explainability
* Evidence-grounded RAG
* Investigator dashboard
* Human verification
* Audit and provenance

Advanced capabilities such as complete mobile-device acquisition, forensic disk imaging, direct access to real banking systems, custom large-language-model training, large-scale model training, or deployment as court-admissible production software are outside the initial scope.

## **38\. Future Enhancement: Timeline Reconstruction**

Timeline reconstruction can be added as a future enhancement if sufficient development time becomes available.

A future timeline module could collect available temporal information from CCTV, mobile devices, network systems, transactions, GPS records, and other sources and organize the resulting events chronologically.

It could additionally support:

* Timestamp normalization
* Temporal conflict detection
* Event ordering
* Timeline visualization
* Temporal gap analysis
* Temporal proximity-based triage

Because the current architecture already stores timestamps and event information within the common evidence representation, a future timeline module can be added without fundamentally redesigning the entire system.

Therefore, timeline reconstruction remains a possible future extension rather than a mandatory component of the initial implementation.

## **39\. Final Working of EVORA**

The proposed working of the system can be summarized as:

Evidence Collection

↓

Evidence ID and Metadata Recording

↓

Evidence Hash and Provenance

↓

Multimodal Evidence Processing

↓

Entity and Event Extraction

↓

Common Evidence Representation

↓

Initial Evidence Triage

↓

Forensic Knowledge Graph

↓

Cross-Source Relationship Analysis

↓

Evidence Gap / Conflict / Anomaly Analysis

↓

Reliability and Uncertainty Analysis

↓

Evidence Cluster Formation

↓

Adaptive Evidence Re-Triage

↓

Explainable AI

↓

Evidence-Grounded RAG

↓

Investigator Dashboard

↓

Human Verification

↓

Audit and Provenance Logging

↓

Further Investigation

This workflow allows EVORA to move beyond simple evidence storage and analysis toward an adaptive investigation-support architecture.

## **40\. Conclusion**

EVORA presents an AI-assisted approach to heterogeneous forensic evidence analysis in which evidence from different sources is collected, preserved, extracted, normalized, connected, prioritized, analyzed, explained, and presented within a unified investigative workflow.

The system combines multimodal information extraction with a common evidence representation, forensic knowledge graph, cross-source relationship analysis, adaptive evidence triage, evidence cluster prioritization, evidence-gap detection, anomaly detection, conflict identification, reliability assessment, uncertainty representation, alternative-hypothesis reasoning, explainable AI, evidence-grounded retrieval, and provenance tracking.

Its primary objective is not to replace established forensic systems or make autonomous judgments, but to investigate how heterogeneous evidence can be integrated into an explainable, adaptive, and auditable decision-support framework.

The central research concept is the adaptive investigation loop:

Evidence → Triage → Analysis → New Information → Re-Triage → Further Analysis → Human Verification

By maintaining links between analytical findings and their underlying evidence, explaining why evidence receives investigative priority, recording provenance, and keeping the investigator involved in the verification process, EVORA provides a research-oriented foundation for exploring transparent and evidence-grounded artificial intelligence in forensic investigation.

Timeline reconstruction can subsequently be incorporated as a future enhancement if development time permits.
