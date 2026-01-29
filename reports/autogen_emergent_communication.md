# Research Gap Analysis Report

## EXECUTION METADATA
Generated: 2025
Agent Configuration: 4-agent swarm (Paper Reading → Approach Analysis → Contradiction Detection → Gap Synthesis)
Analysis Scope: 12 papers on emergent communication in multi-agent reinforcement learning

## ANALYZED PAPERS (12 papers)

### Paper 1: "Emergent Language: A Survey and Taxonomy"
    Authors: Jannik Peters, Constantin Waubert de Puiseau, Hasan Tercan, Arya Gopikrishnan, Gustavo Adolpho Lucas De Carvalho, Christian Bitter, Tobias Meisen
    Published: 2024-09-04
    ArXiv: 2409.02645v2
    Key Contribution: Comprehensive survey of 181 publications with terminology analysis, evaluation methods, and research gap identification

### Paper 2: "Speaking Your Language: Spatial Relationships in Interpretable Emergent Communication"
    Authors: Olaf Lipinski, Adam J. Sobey, Federico Cerutti, Timothy J. Norman
    Published: 2024-06-11
    ArXiv ID: Not specified
    Key Contribution: First demonstration of spatial reference emergence (90%+ accuracy) with human interpretability validation (78%+ accuracy)

### Paper 3: "Learning Translations: Emergent Communication Pretraining for Cooperative Language Acquisition"
    Authors: Dylan Cope, Peter McBurney
    Published: 2024-02-26
    ArXiv ID: Not specified
    Key Contribution: Introduced CLAP framework for agents learning to translate between emergent protocols and target community protocols

### Paper 4: "It's About Time: Temporal References in Emergent Communication"
    Authors: Olaf Lipinski, Adam J. Sobey, Federico Cerutti, Timothy J. Norman
    Published: 2023-10-10
    ArXiv ID: Not specified
    Key Contribution: First temporal reference emergence (95%+ agents) achieved through minimal architectural change (batching method)

### Paper 5: "Emergent Communication: Generalization and Overfitting in Lewis Games"
    Authors: Mathieu Rita, Corentin Tallec, Paul Michel, Jean-Bastien Grill, Olivier Pietquin, Emmanuel Dupoux, Florian Strub
    Published: 2022-09-30
    ArXiv ID: Not specified
    Key Contribution: Analytical decomposition of Lewis game objectives into co-adaptation loss + information loss, showing overfitting control improves compositionality

### Paper 6: "Recommendations for Systematic Research on Emergent Language"
    Authors: Brendon Boldt, David Mortensen
    Published: 2022-06-22
    ArXiv ID: Not specified
    Key Contribution: Framework distinguishing science vs. engineering goals with methodological recommendations for systematic research

### Paper 7: "The Emergence of Complex Behavior in Large-Scale Ecological Environments"
    Authors: Joseph Bejjani, Chase Van Amburg, Chengrui Wang, Chloe Huangyuan Su, Sarah M. Pratt, Yasin Mazloumi, Naeem Khoshnevis, Sham M. Kakade, Kianté Brantley, Aaron Walsman
    Published: 2025-10-21
    ArXiv ID: Not specified
    Key Contribution: Scaled emergent behavior simulations to 60,000+ agents using evolutionary dynamics, demonstrating scale-dependent behavior emergence

### Paper 8: "Emergent Quantized Communication"
    Authors: Boaz Carmeli, Ron Meir, Yonatan Belinkov
    Published: 2022-11-04
    ArXiv ID: Not specified
    Key Contribution: Quantization framework for discrete communication enabling end-to-end training with superior performance to RL/Gumbel-softmax

### Paper 9: "Language Evolution with Deep Learning"
    Authors: Mathieu Rita, Paul Michel, Rahma Chaabouni, Olivier Pietquin, Emmanuel Dupoux, Florian Strub
    Published: 2024-03-18
    ArXiv ID: Not specified
    Key Contribution: Overview of deep learning for language emergence compared to classical methods (genetic algorithms, rule-based systems)

### Paper 10: "On the role of population heterogeneity in emergent communication"
    Authors: Mathieu Rita, Florian Strub, Jean-Bastien Grill, Olivier Pietquin, Emmanuel Dupoux
    Published: 2022-04-27
    ArXiv ID: Not specified
    Key Contribution: Resolved simulation-sociolinguistics discrepancy by showing heterogeneous populations (training speed variation) develop more structured language

### Paper 11: "Inductive Bias for Emergent Communication in a Continuous Setting"
    Authors: John Isak Fjellvang Villanger, Troels Arnfred Bojesen
    Published: 2023-06-06
    ArXiv ID: Not specified
    Key Contribution: Introduced inductive bias for continuous message spaces in multi-agent RL with beneficial effects on protocol quality

### Paper 12: "Emergent Discrete Communication in Semantic Spaces"
    Authors: Mycal Tucker, Huao Li, Siddharth Agrawal, Dana Hughes, Katia Sycara, Michael Lewis, Julie Shah
    Published: 2021-08-04
    ArXiv ID: Not specified
    Key Contribution: Word-embedding-inspired approach enabling zero-shot human-agent communication and semantic token clustering

## RESEARCH FIELD OVERVIEW

Emergent communication represents a frontier in artificial intelligence where autonomous agents develop their own communication protocols through interaction, without explicit language supervision. Unlike traditional natural language processing that learns from human-generated text, this field explores how communication systems can arise from cooperative task pressures in multi-agent reinforcement learning environments. The research spans two complementary goals: (1) understanding the evolutionary mechanisms that shaped human language, and (2) engineering effective communication protocols for AI systems that may surpass limitations of natural language.

The field has progressed from foundational studies using simple referential games (2021-2022) to specialized investigations of specific linguistic properties like spatial [2] and temporal [4] references (2023-2024), and recently to massive-scale ecological simulations with over 60,000 agents [7] (2025). Key challenges include achieving human-like properties such as compositionality, generalization to novel situations, and interpretability by humans. The research reveals tensions between continuous and discrete communication modalities, the role of population dynamics, and the minimal architectural or training modifications necessary to induce desired linguistic structures.

Current work demonstrates that scale matters—both in population size [7, 10] and environmental complexity—but also that subtle factors like population heterogeneity [10] and architectural choices [4] can dramatically affect what communication properties emerge. The field has reached a maturation point where comprehensive surveys [1, 6] call for more systematic, reproducible research practices to move beyond exploratory studies toward measurable progress on well-defined problems.

## MAJOR APPROACHES

### Approach 1: Game-Theoretic Communication Frameworks (Papers: [2], [4], [5], [10])

This approach uses structured communication games where agents must coordinate on protocols to solve cooperative tasks. Lewis signaling games [5, 10] serve as the foundational framework, where speakers send messages about observations to listeners who must take appropriate actions. Recent extensions specialize these games for specific linguistic phenomena: referential games for spatial relationships [2] achieving 90%+ accuracy, and temporal referential games [4] where 95%+ of agents develop temporal references. Paper [5] provides critical analytical insight by decomposing the standard objective into co-adaptation loss (agents coordinating) and information loss (message informativeness), revealing two sources of overfitting that undermine language structure. Paper [10] explores how population heterogeneity in Lewis Games affects language emergence, showing that training speed asymmetries produce more structured protocols in larger populations.

### Approach 2: Continuous-Discrete Communication Spectrum (Papers: [8], [11], [12])

These papers address the fundamental tension between continuous message spaces (easier to train with gradient descent) and discrete tokens (desired for interpretability and human-like communication). Paper [8] proposes quantization as a unifying framework that "runs the gamut from continuous to discrete," enabling end-to-end training with superior performance to reinforcement learning or Gumbel-softmax approximations. Paper [12] draws inspiration from NLP word embeddings to create discrete tokens derived from learned continuous semantic spaces, enabling zero-shot understanding and successful human-agent communication. Paper [11] introduces inductive biases specifically designed for continuous message protocols in multi-agent RL settings, demonstrating beneficial effects on communication quality in Negotiation and Sequence Guess environments.

### Approach 3: Large-Scale Population and Evolutionary Dynamics (Papers: [7], [10])

This approach investigates how scale and population characteristics shape emergent behaviors. Paper [7] represents the most ambitious scaling effort, simulating over 60,000 agents with evolved neural network policies in ecological environments without explicit rewards—agents reproduce, mutate, and are selected based on survival. This reveals behaviors like long-range resource extraction and predation that emerge only at sufficient scale, with larger environments increasing stability and consistency. Paper [10] examines population heterogeneity at smaller scales, demonstrating that homogeneous agent populations fail to reproduce sociolinguistic patterns where larger populations develop more structured language, but introducing training speed heterogeneity resolves this discrepancy.

### Approach 4: Zero-Shot Generalization and Transfer (Papers: [3], [12])

These papers address the limitation that emergent protocols are typically specialized to training communities and fail when encountering novel agents. Paper [3] introduces Cooperative Language Acquisition Problems (CLAP), where a "joiner" agent learns from interaction datasets to translate between its own emergent protocol and a target community's protocol, comparing imitation learning versus emergent communication pretraining with translation learning (ECTL). Paper [12] demonstrates that agents using semantic space embeddings can effectively respond to novel human communication and that humans can understand unlabeled emergent agent communication, outperforming one-hot encoding approaches.

### Approach 5: Architectural and Training Modifications (Papers: [4], [5], [11])

This approach systematically varies agent architecture or training procedures to induce specific linguistic properties. Paper [4] demonstrates that modifying the batching method (a minimal architectural change) enables temporal reference emergence in 95%+ of agents, while loss function changes alone are insufficient. Paper [5] shows that controlling overfitting on the co-adaptation loss component through training modifications yields more compositional languages with better generalization, without architectural changes. Paper [11] designs inductive biases for continuous communication that improve protocol quality when combined with reinforcement learning.

### Approach 6: Meta-Research and Methodological Frameworks (Papers: [1], [6], [9])

These foundational papers provide surveys, taxonomies, and methodological guidance for the field. Paper [1] surveys 181 publications, analyzing terminology, evaluation methods, and identifying research gaps, serving as a comprehensive reference. Paper [6] distinguishes between science goals (understanding language evolution) and engineering goals (building effective communication systems), recommending systematic research practices to move beyond exploratory work toward measurable progress. Paper [9] positions deep learning approaches within the broader history of computational language emergence modeling, comparing them to genetic algorithms, Bayesian agents, and rule-based systems.

## KEY FINDINGS & CONSENSUS

### Consensus 1: Limitations of One-Hot Encoding for Discrete Communication (Papers: [8], [12])
Both papers critique standard one-hot vector representations as preventing zero-shot understanding and semantic relationships. They independently propose continuous-discrete hybrid approaches—quantization [8] and semantic embeddings [12]—that outperform traditional discrete methods while maintaining interpretability.

### Consensus 2: Compositionality and Generalization Remain Fundamental Challenges (Papers: [2], [4], [5], [10])
Multiple papers acknowledge that emergent languages often lack compositional structure and fail to generalize beyond training conditions. Paper [5] identifies overfitting on co-adaptation loss as a root cause; Papers [2] and [4] show that achieving specific compositional properties (spatial/temporal references) requires targeted interventions; Paper [10] demonstrates that population heterogeneity helps but doesn't fully solve the problem.

### Consensus 3: Scale Enables Complexity and Stability (Papers: [7], [10])
Both papers demonstrate that larger populations and environments enable more complex behaviors and more stable/structured languages. Paper [7] shows certain behaviors emerge only at scales of 60,000+ agents, while Paper [10] shows that population size effects are modulated by heterogeneity factors. Both agree that scale is necessary but not sufficient—environmental and population characteristics matter.

### Consensus 4: Human Interpretability Validates Linguistic Structure (Papers: [2], [12])
Both papers use human interpretability as a validation metric, with Paper [2] achieving 78%+ accuracy when humans communicate with receiver agents using interpreted lexicons, and Paper [12] demonstrating that humans can understand unlabeled emergent communication. This consensus establishes human-agent communication as a gold standard for evaluating whether emergent protocols have genuine linguistic structure.

### Consensus 5: Zero-Shot Coordination Is Difficult But Critical (Papers: [3], [5])
Papers agree that protocols specialized to training communities overfit and fail when encountering novel agents. Paper [3] explicitly addresses this with translation learning frameworks, while Paper [5] shows that generalization failures stem from overfitting on co-adaptation loss. Both identify this as a central challenge requiring new approaches.

### Consensus 6: Field Requires Systematic Methodological Standards (Papers: [1], [6], [9])
All three meta-research papers emphasize that the field has been exploratory and lacks standardized evaluation metrics, reproducible experimental designs, and clear problem definitions. They call for systematic research practices to enable measurable progress and meaningful comparisons across studies.

## CONTRADICTIONS & OPEN DEBATES

### Contradiction 1: Performance of Discrete Communication Methods

- **Paper [8]** claims: "RL algorithms and Gumbel-softmax result in poor performance compared to fully continuous communication"—suggesting discrete approaches are fundamentally limited
- **Paper [12]** demonstrates: "Our technique optimizes communication over a wide range of scenarios, whereas one-hot tokens are only optimal under restrictive assumptions"—showing discrete tokens from semantic spaces achieve excellent performance

**Analysis:** This represents a genuine methodological disagreement about the feasibility of discrete communication. The resolution may lie in distinguishing between naive discrete methods (one-hot, Gumbel-softmax) that both papers criticize versus sophisticated approaches (quantization [8], semantic embeddings [12]) that both papers propose. However, the papers don't directly compare their methods, leaving open which approach to discrete communication is superior.

### Contradiction 2: Necessary Conditions for Linguistic Property Emergence

- **Paper [4]** asserts: "Altering the loss function is insufficient for temporal references to emerge; rather, architectural changes are necessary"—claiming architecture is essential
- **Paper [5]** achieves: "When we control for overfitting on co-adaptation loss, we recover desired properties...they are more compositional"—obtaining linguistic properties through loss decomposition and training modifications without architectural changes

**Analysis:** This contradiction concerns what interventions are necessary versus sufficient for different linguistic properties. The resolution may be that different properties (temporal references vs. compositionality) require different interventions. Alternatively, Paper [4]'s "minimal architectural change" (batching method) might be reframed as a training modification rather than a fundamental architectural change. This debate remains unresolved regarding general principles of what drives linguistic structure emergence.

### Contradiction 3: Population Size Effects (Resolved Within Literature)

- **Paper [10]** initially notes: Neural simulations fail to reproduce sociolinguistic findings that larger populations develop more structured language
- **Paper [10]** resolution: Introducing population heterogeneity (training speed variation) allows larger populations to develop more structured language, aligning with sociolinguistic patterns
- **Paper [7]** confirms: Larger scales (60,000+ agents) increase stability and consistency of emergent behaviors

**Analysis:** This represents an initially apparent contradiction between sociolinguistics and computational simulations that Paper [10] resolves by identifying population heterogeneity as the critical missing factor. This shows the field successfully debugging initial failures to reproduce expected patterns.

### Open Debate 1: Continuous vs. Discrete Message Spaces

Papers [8], [11], and [12] propose different solutions to bridging continuous-discrete communication, but lack direct empirical comparisons. The field lacks consensus on whether quantization [8], inductive biases for continuous messages [11], or semantic embeddings [12] represents the best path forward.

### Open Debate 2: Evolutionary vs. Reinforcement Learning Paradigms

Paper [7] uses evolutionary dynamics without explicit rewards (reproduction/mutation/selection), while most other papers use multi-agent RL with explicit reward signals. The relative advantages of these paradigms for achieving different types of emergent behaviors remain unexplored, as Paper [7] operates at dramatically different scales and focuses on ecological behaviors rather than communication protocols.

## IDENTIFIED RESEARCH GAPS

### Gap 1: Evaluation Standardization and Cross-Study Comparability
**Category:** Methodological Gap

**Description:** Despite Papers [1] and [6] calling for systematic evaluation standards, the field lacks unified

 benchmarks, shared evaluation metrics, or standardized experimental protocols. Each study uses custom environments, different metrics for compositionality, and varied definitions of success. Paper [1] surveys 181 publications and identifies inconsistent evaluation methods as a critical gap; Paper [6] explicitly recommends systematic research practices that have not been widely adopted.

**Evidence:** Paper [1] analyzes evaluation methods across 181 publications and notes their inconsistency. Paper [6] states that research has been "largely exploratory" and lacks "well-defined problems to be solved." No paper in the analyzed set references a common benchmark or evaluation suite that others use.

**Opportunity:** Develop standardized evaluation frameworks that enable direct comparison across studies, similar to how ImageNet or GLUE benchmarks transformed computer vision and NLP. This would allow the field to measure progress objectively rather than relying on isolated demonstrations.

---

### Gap 2: Integration of Spatial and Temporal References
**Category:** Linguistic Property Gap

**Description:** Papers [2] and [4] independently achieve spatial and temporal references respectively, but no research explores agents that must communicate about both spatial AND temporal relationships simultaneously (e.g., "the object that was on the left is now on the right"). This represents a missing combination of demonstrated capabilities.

**Evidence:** Paper [2] achieves 90%+ accuracy on spatial relationships; Paper [4] achieves 95%+ temporal reference emergence. However, both operate in isolated domains. Natural language routinely combines spatial and temporal deixis (e.g., "the car that was there yesterday"), but no analyzed paper tests this combined capability.

**Opportunity:** Design environments requiring spatiotemporal communication (e.g., tracking moving objects across positions and time), testing whether agents can develop languages with both properties simultaneously or whether these capabilities interfere with each other. This would reveal whether different linguistic properties compete for representational capacity.

---

### Gap 3: Reconciliation of Architecture vs. Training Debates
**Category:** Theoretical Gap

**Description:** Papers [4] and [5] present contradictory findings about whether architectural changes or training/loss modifications are necessary for linguistic properties to emerge. No systematic study isolates these factors across multiple linguistic properties to establish general principles.

**Evidence:** Paper [4] claims "architectural changes are necessary" for temporal references, requiring modified batching. Paper [5] achieves compositionality through "controlling overfitting on co-adaptation loss" without architectural changes. The field lacks understanding of when each intervention type is required.

**Opportunity:** Conduct controlled ablation studies testing the same linguistic property (e.g., compositionality, spatial reference, temporal reference) under three conditions: (1) architectural changes only, (2) training/loss modifications only, (3) both combined. This would clarify whether the contradiction stems from different properties requiring different interventions or from incomplete analysis in the original papers.

---

### Gap 4: Heterogeneity Beyond Training Speed
**Category:** Population Dynamics Gap

**Description:** Paper [10] demonstrates that training speed heterogeneity enables larger populations to develop more structured language, but this represents only one dimension of heterogeneity. Unexplored factors include: architectural heterogeneity (different agent designs), sensory heterogeneity (different observation capabilities), goal heterogeneity (different objectives), and experiential heterogeneity (different training histories).

**Evidence:** Paper [10] explicitly tests only "learning speed" as a heterogeneity factor after identifying it as a key diversity component. The paper acknowledges this as introducing population heterogeneity but doesn't explore other dimensions. Paper [7] uses evolutionary variation but doesn't systematically analyze which heterogeneity factors matter.

**Opportunity:** Systematically vary heterogeneity dimensions in Lewis Games or referential games, testing whether architectural diversity (e.g., mixing CNN and transformer agents) or goal diversity (e.g., agents with partially overlapping objectives) produces different linguistic structures than training speed variation alone. This could reveal whether heterogeneity effects are general or specific to particular diversity types.

---

### Gap 5: Scale Transition Dynamics
**Category:** Scaling Gap

**Description:** Paper [7] operates at 60,000+ agents while most other papers operate at 2-10 agents. No research systematically examines the transition dynamics: at what population sizes do qualitative changes in linguistic structure occur? Are there critical thresholds (e.g., 10, 100, 1000 agents) where new properties emerge?

**Evidence:** Paper [7] shows "some behaviors appear only in sufficiently large environments and populations" but doesn't identify specific thresholds. Papers [2], [4], [5], [10] operate at small scales (typically 2-agent or small populations). The gap between these scales remains unexplored, making it unclear whether findings from small-scale studies generalize to larger populations.

**Opportunity:** Conduct systematic scaling studies with populations of 2, 10, 50, 100, 500, 1000, 5000+ agents, measuring when specific linguistic properties (compositionality, spatial reference, temporal reference, zero-shot generalization) emerge or stabilize. This would identify critical population sizes for different capabilities and inform efficient experimental design.

---

### Gap 6: Cross-Method Comparison of Continuous-Discrete Approaches
**Category:** Methodological Gap

**Description:** Papers [8], [11], and [12] propose three different solutions to continuous-discrete communication (quantization, inductive biases, semantic embeddings), but no study directly compares these approaches on the same tasks with the same evaluation metrics.

**Evidence:** Paper [8] proposes quantization; Paper [11] proposes inductive biases for continuous messages; Paper [12] proposes semantic embeddings. Each paper evaluates on different environments (Paper [8] on general multi-agent tasks, Paper [11] on Negotiation/Sequence Guess, Paper [12] on decision-theoretic frameworks) with different metrics. Papers [8] and [12] contradict each other on discrete communication performance but test different methods.

**Opportunity:** Implement all three approaches (quantization, inductive biases, semantic embeddings) in the same experimental frameworks used in Papers [2], [4], and [5] (referential games, Lewis games, temporal tasks), comparing their compositionality, generalization, human interpretability, and training efficiency. This would resolve the open debate about which approach to continuous-discrete communication is most promising.

---

### Gap 7: Translation Mechanisms at Scale
**Category:** Transfer Learning Gap

**Description:** Paper [3] introduces translation learning for joining new communities (CLAP framework), but only at small scales with homogeneous populations. No research examines translation in heterogeneous populations [10] or at ecological scales [7], despite both papers showing that population characteristics significantly affect language structure.

**Evidence:** Paper [3] demonstrates CLAP with standard emergent communication setups but doesn't incorporate population heterogeneity findings from Paper [10] or test at the scales of Paper [7]. Paper [3] acknowledges that agents learn "protocols specialized to their training community" but doesn't explore how heterogeneity affects this specialization or whether translation becomes harder/easier in diverse populations.

**Opportunity:** Test CLAP translation learning in heterogeneous populations where agents have different training speeds [10], different architectures, or different sensory capabilities. Investigate whether translation is easier (because more diverse protocols are less idiosyncratic) or harder (because protocols are less consistent across population). This could reveal fundamental principles about protocol standardization in diverse communities.

---

### Gap 8: Human-Agent Communication Beyond Referential Games
**Category:** Application Gap

**Description:** Papers [2] and [12] successfully demonstrate human interpretability and human-agent communication, but only in simple referential games or decision-theoretic frameworks. No research tests whether humans can interpret or participate in the more complex emergent behaviors from ecological simulations [7] or in environments requiring temporal reasoning [4].

**Evidence:** Paper [2] achieves 78%+ human-agent communication accuracy in spatial referential games. Paper [12] shows humans can understand emergent communication in their decision-theoretic setup. However, Paper [7]'s ecological behaviors (predation, long-range resource extraction) and Paper [4]'s temporal references remain untested for human interpretability.

**Opportunity:** Design human-in-the-loop experiments where humans observe agents in ecological environments [7] and attempt to predict their behaviors or communicate warnings (e.g., alert agents about predators), or where humans participate in temporal reasoning tasks [4] alongside agents. This would test whether interpretability scales beyond simple games to complex behaviors, which is critical for real-world human-AI collaboration.

---

### Gap 9: Evolutionary Communication Protocols
**Category:** Paradigm Gap

**Description:** Paper [7] uses evolutionary dynamics (reproduction/mutation/selection) rather than reinforcement learning, showing that scale enables complex behavior emergence without explicit rewards. However, Paper [7] focuses on foraging, predation, and survival behaviors—not explicit communication protocols like those in Papers [2], [4], [5], [10]. No research combines evolutionary dynamics with communication protocol emergence at scale.

**Evidence:** Paper [7] simulates 60,000+ agents with evolutionary dynamics but doesn't explicitly model communication channels or messages between agents—behaviors emerge from environmental pressures alone. Papers using RL (most others) operate at much smaller scales and use explicit communication channels. The gap is the absence of large-scale evolutionary communication protocol studies.

**Opportunity:** Extend Paper [7]'s evolutionary framework by adding explicit communication channels, testing whether communication protocols at 60,000+ agent scales evolve differently than in small-scale RL settings. This would reveal whether evolutionary pressures at scale produce more structured, compositional, or human-interpretable languages than RL optimization, and whether findings from Papers [2], [4], [5] about linguistic properties hold under evolutionary rather than RL training.

---

### Gap 10: Noise, Ambiguity, and Communication Robustness
**Category:** Robustness Gap

**Description:** Paper [12] mentions "noisy environments where other techniques fail," but no systematic study examines how different emergent communication approaches (quantization [8], semantic embeddings [12], spatial references [2], temporal references [4]) degrade under varying noise levels, message corruption, or observational ambiguity.

**Evidence:** Paper [12] briefly notes performance in noisy environments but doesn't systematically vary noise levels or types. No other analyzed paper explicitly manipulates communication noise, channel errors, or observational ambiguity as experimental variables. The field lacks robustness analysis despite real-world communication facing constant interference.

**Opportunity:** Create a robustness benchmark testing all major approaches [2, 4, 5, 8, 10, 11, 12] under controlled noise conditions: (1) message corruption (bits flipped), (2) message loss (dropped messages), (3) observational noise (corrupted inputs), (4) semantic ambiguity (multiple objects matching descriptions). This would identify which approaches are inherently more robust and whether robustness trades off with other properties like compositionality or efficiency.

---

### Gap 11: Compositional Generalization Across Linguistic Properties
**Category:** Generalization Gap

**Description:** Papers demonstrate compositional structure for specific properties (spatial [2], temporal [4], general compositionality [5]), but no research tests whether agents can compositionally generalize across multiple linguistic dimensions simultaneously (e.g., novel combinations of spatial and temporal concepts, or compositional reasoning about properties not seen during training).

**Evidence:** Paper [5] shows agents achieve compositionality within their training domain but doesn't test cross-domain generalization. Paper [2] shows spatial compositionality and Paper [4] shows temporal compositionality, but neither tests whether agents trained on spatial concepts can compositionally acquire temporal ones (or vice versa) with minimal additional training. This differs from human language where compositional structure transfers across domains.

**Opportunity:** Design multi-stage training where agents first learn spatial references [2], then must compositionally extend to temporal references [4] using the same underlying structural principles, measuring transfer efficiency. Compare this to agents trained on both simultaneously or separately, testing whether compositional structure is domain-specific or represents a general principle that transfers. This would reveal whether emergent compositionality is truly systematic (like human language) or merely task-specific pattern matching.

## RECOMMENDED RESEARCH DIRECTIONS

### Research Direction 1: Develop Cross-Environment Standardized Evaluation Suite Building on [1], [2], [4], [5], [6] (Priority: Near-term)

**Gap Addressed:** Evaluation Standardization and Cross-Study Comparability (Gap 1)

**Building On:** Extends Paper [6]'s systematic methodology recommendations and Paper [1]'s analysis of 181 publications' evaluation methods. Incorporates the spatial reference tests from Paper [2], temporal reference tests from Paper [4], and compositionality metrics from Paper [5].

**Concrete Approach:** 
1. **Environment Suite:** Create 5 benchmark environments of increasing complexity:
   - Level 1: Basic referential games (from [5]) testing co-adaptation
   - Level 2: Spatial reference games (from [2]) testing spatial deixis
   - Level 3: Temporal reference games (from [4]) testing temporal deixis
   - Level 4: Combined spatiotemporal games (Gap 2) testing integrated references
   - Level 5: Noisy communication games (Gap 10) testing robustness

2. **Metrics Package:** Implement standardized metrics from Papers [1], [2], [4], [5]:
   - Topographic similarity (compositionality measure from [5])
   - Human interpretability scores (methodology from [2], [12])
   - Generalization accuracy (zero-shot test sets from [5])
   - Message entropy and efficiency (information theory from [5])
   - Robustness under noise (corruption tests)

3. **Reference Implementations:** Provide baseline implementations of key architectures:
   - Standard speaker-listener from [5]
   - Modified batching architecture from [4]
   - Semantic embedding approach from [12]
   - Quantization framework from [8]

**First Steps:** 
1. Catalog all evaluation metrics used across papers [1,2,4,5,10,11,12] and identify the 10 most commonly used or theoretically justified
2. Implement Level 1 and Level 2 environments with 3 baseline architectures and public leaderboard
3. Organize community workshop (building on [6]'s recommendations) to gather feedback and adoption

**Expected Impact:** Enables objective comparison across studies, faster identification of which approaches generalize best, and measurable progress tracking for the field. Would resolve the methodological gap identified by Papers [1] and [6] as fundamental to field maturation.

---

### Research Direction 2: Systematic Spatiotemporal Communication Testbed Extending [2] and [4] (Priority: Near-term)

**Gap Addressed:** Integration of Spatial and Temporal References (Gap 2)

**Building On:** Combines Paper [2]'s spatial referential game achieving 90%+ accuracy with Paper [4]'s temporal reference architecture achieving 95%+ emergence. Tests whether linguistic properties can coexist or interfere.

**Concrete Approach:**
1. **Environment Design:** Modify Paper [2]'s grid-based spatial environment to include temporal dynamics:
   - Objects move between positions over timesteps
   - Agents must communicate about objects' past/present/future locations
   - Tasks require statements like "the object that was left of X is now right of Y"

2. **Architecture Testing:** Compare three conditions:
   - Paper [2]'s spatial-only architecture on spatiotemporal tasks
   - Paper [4]'s temporal-only architecture (modified batching) on spatiotemporal tasks
   - Combined architecture incorporating both spatial biases [2] and temporal batching [4]

3. **Analysis Protocol:** Use Paper [2]'s collocation measures to identify whether agents develop:
   - Separate spatial and temporal markers (compositional)
   - Fused spatiotemporal markers (holistic)
   - Sequential references (temporal then spatial, or vice versa)

**First Steps:**
1. Implement Paper [2]'s environment with added temporal dynamics (3-5 timesteps of object motion)
2. Train Paper [2]'s best architecture on new environment, measuring spatial vs. temporal reference accuracy separately
3. Compare message structure (using collocation analysis from [2]) to identify whether spatial/temporal markers emerge or interfere

**Expected Impact:** Reveals whether linguistic properties compete for representational capacity or can coexist, informing whether emergent languages can scale to natural language complexity. Addresses a fundamental question about composability of linguistic properties that neither Paper [2] nor [4] tested.

---

### Research Direction 3: Controlled Ablation Study of Architecture vs. Training Modifications for Linguistic Properties, Resolving [4] vs. [5] Contradiction (Priority: Near-term)

**Gap Addressed:** Reconciliation of Architecture vs. Training Debates (Gap 3)

**Building On:** Directly tests the contradiction between Paper [4]'s claim that "architectural changes are necessary" and Paper [5]'s demonstration that training modifications suffice for compositionality. Uses environments and metrics from both papers.

**Concrete Approach:**
1. **Target Properties:** Test three linguistic properties across interventions:
   - Compositionality (Paper [5]'s target)
   - Temporal references (Paper [4]'s target)
   - Spatial references (Paper [2]'s target)

2. **Intervention Matrix (3x3 design):**
   - **Architecture-only:** Paper [4]'s batching changes WITHOUT loss modifications
   - **Training-only:** Paper [5]'s overfitting control WITHOUT architecture changes
   - **Combined:** Both architectural and training modifications together

3. **Environments:** 
   - Lewis Games (from [5]) for compositionality
   - Temporal referential games (

from [4]) for temporal references
   - Spatial referential games (from [2]) for spatial references

4. **Analysis:** For each property-intervention combination, measure:
   - Emergence success rate (% of runs achieving property)
   - Training efficiency (epochs to achieve property)
   - Robustness (performance under noise from Gap 10)
   - Generalization (zero-shot accuracy from [5])

**First Steps:**
1. Replicate Paper [5]'s baseline Lewis Game results and Paper [4]'s temporal reference results to establish reproducibility
2. Implement Paper [4]'s batching modification in Paper [5]'s Lewis Game environment (cross-application)
3. Implement Paper [5]'s loss decomposition in Paper [4]'s temporal environment (cross-application)
4. Run 3x3 matrix with 10 seeds per condition

**Expected Impact:** Resolves the field's confusion about what interventions are necessary vs. sufficient for different linguistic properties. Provides actionable guidance for researchers designing new experiments: "For temporal references, use architectural changes [4]; for compositionality, use training modifications [5]; for spatial references, architecture suffices [2]" or discovers that effects are universal.

---

### Research Direction 4: Multi-Dimensional Heterogeneity Effects in Population Dynamics, Extending [10] and [7] (Priority: Medium-term)

**Gap Addressed:** Heterogeneity Beyond Training Speed (Gap 4)

**Building On:** Paper [10] demonstrates training speed heterogeneity enables structured language in larger populations. Paper [7] uses evolutionary variation at massive scale but doesn't analyze which heterogeneity dimensions matter. This direction systematically varies multiple heterogeneity dimensions.

**Concrete Approach:**
1. **Heterogeneity Dimensions (5 factors):**
   - Training speed variation (Paper [10]'s tested factor - baseline)
   - Architectural heterogeneity (mix CNN, RNN, Transformer agents)
   - Sensory heterogeneity (agents observe different feature subsets)
   - Goal heterogeneity (agents have partially overlapping objectives)
   - Experiential heterogeneity (agents trained on different task distributions)

2. **Experimental Design:** Use Paper [10]'s Lewis Game framework with populations of 10, 50, 100 agents
   - Control condition: Homogeneous populations (all dimensions identical)
   - Single-dimension: Vary each dimension individually
   - Multi-dimension: Combine dimensions (architectural + sensory, goal + experiential, etc.)

3. **Metrics from [10]:** 
   - Language structure (topographic similarity from [5])
   - Protocol stability (consistency across population subgroups)
   - Zero-shot coordination (novel agent pairing success from [3])

4. **Scaling Test:** Apply most effective heterogeneity combinations to Paper [7]'s scale (1000+ agents) to test whether findings transfer to ecological dynamics

**First Steps:**
1. Implement architectural heterogeneity in Paper [10]'s Lewis Game (easiest to implement): mix 3 agent architectures (small CNN, medium RNN, large Transformer)
2. Replicate Paper [10]'s training speed results as baseline comparison
3. Measure whether architectural diversity produces more/less/different structure than training speed diversity using Paper [10]'s analysis methods

**Expected Impact:** Reveals whether heterogeneity effects are general (any diversity helps) or specific (only certain dimensions matter). Informs practical multi-agent system design: should we intentionally diversify agent architectures, or is training variation sufficient? Provides theoretical insight into whether biological diversity's effects on human language are captured by any computational diversity or require specific types.

---

### Research Direction 5: Critical Population Size Thresholds for Linguistic Property Emergence, Bridging [2,4,5,10] and [7] (Priority: Medium-term)

**Gap Addressed:** Scale Transition Dynamics (Gap 5)

**Building On:** Paper [7] operates at 60,000+ agents showing scale-dependent emergence; Papers [2,4,5,10] operate at 2-10 agents. This direction systematically maps the transition zone to identify critical thresholds where linguistic properties emerge.

**Concrete Approach:**
1. **Scale Ladder (logarithmic sampling):** Test populations of 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000 agents

2. **Linguistic Properties (from Papers [2,4,5]):**
   - Compositionality (topographic similarity from [5])
   - Spatial references (accuracy from [2])
   - Temporal references (emergence rate from [4])
   - Zero-shot generalization (novel pair success from [3,5])

3. **Environments:** Use standardized suite from Direction 1:
   - Lewis Games [5] for compositionality
   - Spatial referential games [2] for deixis
   - Temporal referential games [4] for temporal structure

4. **Heterogeneity Control:** Apply Paper [10]'s training speed heterogeneity at all scales to ensure fair comparison (homogeneous populations confound scale effects)

5. **Computational Strategy:** Use Paper [7]'s simulator optimizations to make large-scale runs feasible

**First Steps:**
1. Implement Paper [5]'s Lewis Game with population size as parameter (currently typically 2 agents)
2. Run populations of 2, 10, 50, 100 agents measuring compositionality (topographic similarity)
3. Plot compositionality vs. population size to identify if there are threshold effects or smooth scaling

**Expected Impact:** Identifies "magic numbers" for population-dependent linguistic properties, enabling efficient experimental design (e.g., "test compositionality with 50+ agents minimum"). Reveals whether scale effects are gradual or sudden (phase transitions), informing theories of critical mass in language evolution. Provides practical guidance: "To test property X, you need at least N agents; testing with fewer agents will miss the phenomenon."

---

### Research Direction 6: Unified Continuous-Discrete Benchmark Comparing [8], [11], and [12] (Priority: Near-term)

**Gap Addressed:** Cross-Method Comparison of Continuous-Discrete Approaches (Gap 6)

**Building On:** Papers [8], [11], and [12] propose three different solutions (quantization, inductive biases, semantic embeddings) but never directly compare them. This creates standardized comparison using environments from Papers [2], [4], [5].

**Concrete Approach:**
1. **Three Implementations:**
   - **Quantization (Paper [8]):** Implement their quantization framework exactly as described
   - **Inductive Bias (Paper [11]):** Implement their continuous message bias architecture
   - **Semantic Embeddings (Paper [12]):** Implement their NLP-inspired discrete tokens from continuous space

2. **Test Environments (standardized from Direction 1):**
   - Lewis Games [5] - baseline compositionality
   - Spatial referential games [2] - spatial deixis
   - Temporal referential games [4] - temporal references
   - Negotiation and Sequence Guess [11] - Paper [11]'s original environments
   - Noisy variants (Gap 10) - robustness testing

3. **Comparison Metrics:**
   - Training efficiency (epochs to convergence)
   - Final task performance (accuracy)
   - Compositionality (topographic similarity from [5])
   - Human interpretability (methodology from [2,12])
   - Robustness (noise degradation)
   - Zero-shot generalization (novel task variants from [5])

4. **Theoretical Analysis:** Use Paper [5]'s decomposition (co-adaptation + information loss) to analyze why different methods succeed/fail

**First Steps:**
1. Implement all three methods in Paper [5]'s Lewis Game (simplest environment, well-characterized)
2. Measure task accuracy, compositionality, and training time for each method
3. Publish implementation as open-source library with unified API enabling easy method swapping

**Expected Impact:** Definitively resolves the contradiction between Papers [8] and [12] about discrete communication performance by testing both methods identically. Provides practitioners with evidence-based guidance on which approach to use for their application. May reveal that different methods excel in different scenarios (e.g., quantization for efficiency, semantic embeddings for interpretability), enabling hybrid approaches.

---

### Research Direction 7: Heterogeneous Population Translation Learning Combining [3] and [10] (Priority: Medium-term)

**Gap Addressed:** Translation Mechanisms at Scale (Gap 7)

**Building On:** Paper [3] introduces CLAP translation learning for joining communities but tests only homogeneous populations. Paper [10] shows heterogeneity fundamentally changes language structure. This tests whether translation is easier or harder in diverse populations.

**Concrete Approach:**
1. **Population Conditions (from Paper [10]):**
   - Homogeneous communities (Paper [3]'s original setup - baseline)
   - Training-speed heterogeneous communities (Paper [10]'s tested condition)
   - Architectural heterogeneous communities (new - from Direction 4)
   - Multi-dimensional heterogeneous (training + architecture)

2. **Translation Tasks (from Paper [3]):**
   - **Imitation Learning (IL):** Joiner learns from interaction dataset
   - **ECTL:** Joiner trains in self-play then learns translation
   - **New - Heterogeneous ECTL:** Joiner trains with diverse partners (heterogeneous self-play) then translates

3. **Hypotheses:**
   - **H1 (Easier):** Heterogeneous protocols are less idiosyncratic, making translation easier
   - **H2 (Harder):** Heterogeneous protocols are less consistent, making translation harder
   - **H3 (Nonlinear):** Effect depends on heterogeneity type (training vs. architecture)

4. **Environments:** Use Paper [3]'s cooperative tasks and Paper [10]'s Lewis Games

**First Steps:**
1. Replicate Paper [3]'s CLAP results in homogeneous populations (baseline)
2. Train heterogeneous communities using Paper [10]'s training speed variation
3. Apply Paper [3]'s IL and ECTL methods to join heterogeneous communities, measuring translation accuracy compared to homogeneous baseline

**Expected Impact:** Reveals fundamental principles about protocol standardization in diverse communities. If heterogeneity makes translation easier, this suggests diversity naturally produces more generalizable protocols (aligning with human language universals). If harder, this suggests a tension between population diversity and communicative efficiency. Provides practical guidance for multi-agent systems: should we standardize agents to ease integration, or accept diversity and invest in better translation mechanisms?

---

### Research Direction 8: Human-in-the-Loop Interpretability at Scale, Extending [2], [4], [7], [12] (Priority: Medium-term)

**Gap Addressed:** Human-Agent Communication Beyond Referential Games (Gap 8)

**Building On:** Papers [2] and [12] demonstrate human interpretability in simple games (78%+ accuracy). Paper [7] shows complex emergent behaviors at scale. Paper [4] shows temporal reasoning. This tests whether interpretability scales to complexity.

**Concrete Approach:**
1. **Complexity Ladder (3 levels):**
   - **Level 1:** Referential games (Papers [2,12] - replication baseline)
   - **Level 2:** Temporal reasoning games (Paper [4] - novel human testing)
   - **Level 3:** Ecological behaviors (Paper [7] - highly novel)

2. **Human Tasks:**
   - **Level 1:** Predict agent actions given messages (Paper [2]'s method)
   - **Level 2:** Predict temporal sequences (e.g., "will the agent choose object X now or later?")
   - **Level 3:** Describe agent strategies (e.g., "is this agent foraging, predating, or avoiding predators?")

3. **Bidirectional Testing:**
   - **Human→Agent:** Humans generate messages, measure agent understanding (from [2])
   - **Agent→Human:** Agents generate messages, measure human understanding (from [12])

4. **Architectures:** Test all approaches:
   - Standard (baseline)
   - Semantic embeddings (Paper [12] - expects best interpretability)
   - Quantization (Paper [8] - discrete advantage)
   - Spatial/temporal specialized (Papers [2,4] - property-specific)

**First Steps:**
1. Design Level 2 human study: show humans Paper [4]'s temporal referential games, collect judgments on agent intentions
2. Train agents using Paper [4]'s architecture, extract message-meaning pairs
3. Recruit human participants (e.g., via Mechanical Turk) to predict agent behavior from messages, comparing accuracy to Paper [2]'s 78%+ baseline

**Expected Impact:** Determines whether human interpretability is limited to simple games or scales to complex AI behaviors. If humans can interpret ecological behaviors [7], this enables genuine human-AI collaboration in open-ended environments. If interpretability degrades with complexity, this identifies a fundamental limitation requiring new approaches (e.g., hybrid natural+emergent languages, or interpretability-aware training from Direction 1).

---

### Research Direction 9: Evolutionary Communication at Ecological Scale, Combining [7] with [2,4,5,10] (Priority: Long-term)

**Gap Addressed:** Evolutionary Communication Protocols (Gap 9)

**Building On:** Paper [7] uses evolutionary dynamics at 60,000+ agents but doesn't model explicit communication. Papers [2,4,5,10] study communication protocols but at small scales with RL. This combines evolutionary dynamics with communication protocol emergence.

**Concrete Approach:**
1. **Environment Extension:** Modify Paper [7]'s ecological simulator to add communication channels:
   - Agents can send messages to nearby agents (local communication)
   - Agents can broadcast to visible agents (public communication)
   - Message production has fitness cost (energy expenditure)

2. **Evolutionary Pressures:** Communication must provide survival/reproduction advantage:
   - Coordinated hunting (predation efficiency)
   - Alarm calls (predator avoidance)
   - Resource sharing (cooperative foraging)

3. **Linguistic Property Measurement (from Papers [2,4,5]):**
   - Compositionality (topographic similarity from [5])
   - Spatial references (collocation analysis from [2])
   - Temporal references (sequence analysis from [4])
   - Protocol stability across generations

4. **Comparison:** Train equivalent populations with:
   - Evolutionary dynamics (Paper [7]'s method)
   - Multi-agent RL (Papers [2,4,5,10]'s method)
   - Hybrid (RL within lifetime, evolution across generations)

**First Steps:**
1. Implement simple communication channel in Paper [7]'s simulator: agents broadcast 1 discrete token per timestep
2. Add fitness incentive: agents that coordinate catches (both near prey after communication) gain reproduction bonus
3. Measure whether any systematic protocols emerge over 10,000 generations, analyzing message-behavior correlations

**Expected Impact:** Reveals whether evolutionary pressures at scale produce fundamentally different communication protocols than RL optimization. If evolutionary dynamics yield more structured, compositional, or generalizable languages, this suggests RL's rapid optimization may be counterproductive for linguistic structure. If results are similar, this validates that RL findings [2,4,5,10] transfer to more biologically plausible scenarios. Addresses Paper [6]'s science goal: understanding natural language evolution through realistic simulation.

---

### Research Direction 10: Comprehensive Robustness Benchmark for Emergent Communication, Building on [12] and All Approaches (Priority: Near-term)

**Gap Addressed:** Noise, Ambiguity, and Communication Robustness (Gap 10)

**Building On:** Paper [12] mentions noisy environments but doesn't systematically study robustness. This creates standardized robustness evaluation for all approaches [2,4,5,8,10,11,12].

**Concrete Approach:**
1. **Noise Dimensions (4 types):**
   - **Message corruption:** Bit flips, token substitutions (0%, 5%, 10%, 20%, 50% corruption rates)
   - **Message loss:** Dropped messages (0%, 10%, 25%, 50% loss rates)
   - **Observational noise:** Gaussian noise added to inputs (σ = 0, 0.1, 0.2, 0.5)
   - **Semantic ambiguity:** Multiple objects matching descriptions (varies per environment)

2. **Approaches Tested (7 methods):**
   - Quantization (Paper [8])
   - Semantic embeddings (Paper [12])
   - Inductive bias continuous (Paper [11])
   - Spatial-specialized (Paper [2])
   - Temporal-specialized (Paper [4])
   - Standard Lewis Game baseline (Paper [5])
   - Heterogeneous populations (Paper [10])

3. **Environments (from Direction 1 suite):**
   - Lewis Games [5]
   - Spatial referential [2]
   - Temporal referential [4]

4. **Robustness Metrics:**
   - Performance degradation curves (accuracy vs. noise level)

   - Catastrophic failure threshold (noise level where accuracy < 50%)
   - Recovery capability (accuracy after noise removed vs. before)
   - Compositional robustness (does structure help or hurt under noise?)

**First Steps:**
1. Implement message corruption module for Paper [5]'s Lewis Game (add Bernoulli noise to messages post-generation)
2. Train baseline agents without noise, then test at 0%, 10%, 25%, 50% corruption
3. Plot performance degradation curves, identifying which architectures degrade gracefully vs. catastrophically

**Expected Impact:** Identifies inherently robust communication approaches, enabling deployment in realistic noisy environments. May reveal robustness-compositionality tradeoffs: if highly compositional languages [5] are fragile to noise while holistic languages are robust, this suggests fundamental tension between linguistic properties. Provides practitioners with robustness profiles: "Use method X for low-noise environments where compositionality matters; use method Y for high-noise environments where robustness is critical."

---

### Research Direction 11: Cross-Domain Compositional Transfer Testing Systematic Compositionality, Extending [2], [4], [5] (Priority: Long-term)

**Gap Addressed:** Compositional Generalization Across Linguistic Properties (Gap 11)

**Building On:** Papers [2], [4], [5] demonstrate compositionality within specific domains (spatial, temporal, general) but don't test whether compositional structure transfers across domains like human language compositionality does.

**Concrete Approach:**
1. **Three-Stage Training:**
   - **Stage 1 (Source Domain):** Train agents on spatial references [2] until 90%+ accuracy
   - **Stage 2 (Transfer):** Introduce temporal references [4] with limited training data (10% of Stage 1 data)
   - **Stage 3 (Novel Combinations):** Test on spatiotemporal combinations never seen (Gap 2)

2. **Transfer Conditions (4 groups):**
   - **Sequential specialists:** Train spatial [2], then temporal [4] separately (baseline - no transfer)
   - **Simultaneous learning:** Train spatial + temporal together from scratch (baseline - full data)
   - **Compositional transfer:** Train spatial, then temporal with 10% data (tests transfer efficiency)
   - **Frozen compositional:** Train spatial, freeze composition mechanisms, train temporal (tests structure reuse)

3. **Compositionality Measurement (from Paper [5]):**
   - Topographic similarity within domains
   - Cross-domain topographic similarity (novel metric)
   - Sample efficiency (accuracy per training sample)
   - Zero-shot novel combinations (spatiotemporal tasks not in training)

4. **Architecture Comparison:**
   - Standard (baseline)
   - Paper [5]'s overfitting-controlled training
   - Paper [4]'s batching modifications
   - Combined (both modifications)

**First Steps:**
1. Train Paper [2]'s spatial architecture to 90%+ accuracy (establish source domain mastery)
2. Freeze agent, introduce Paper [4]'s temporal environment with only 1000 training samples (vs. 10,000 normally)
3. Measure temporal reference emergence rate and compare to baseline (10,000 samples without spatial pretraining)
4. Calculate "transfer efficiency": (pretraining accuracy - no pretraining accuracy) / pretraining data ratio

**Expected Impact:** Determines whether emergent compositionality is domain-general (like human language) or domain-specific (task-specific tricks). If compositional structure transfers efficiently, this validates that emergent languages are developing systematic principles rather than memorizing patterns. If transfer fails, this reveals a fundamental limitation: emergent languages may be compositional within narrow domains but lack the cross-domain systematicity that makes human language so powerful. Informs whether emergent communication can scale to natural language complexity or will always be task-specific.

## SUMMARY

The emergent communication field has made substantial progress from foundational game-theoretic frameworks [5,10] to specialized linguistic properties [2,4] and massive-scale ecological simulations [7]. However, critical gaps remain: the field lacks standardized evaluation preventing cross-study comparison [1,6]; linguistic properties have been demonstrated in isolation but never integrated [2,4]; contradictions exist about whether architectural or training modifications drive emergence [4 vs. 5]; and scale transitions remain uncharted between small experiments (2-10 agents) and massive simulations (60,000+ agents). The most promising research directions combine demonstrated capabilities—testing spatiotemporal communication [2+4], resolving architecture-training debates through controlled ablations [4,5], systematically mapping scale effects [7,10], and benchmarking continuous-discrete approaches [8,11,12]. Near-term priorities should focus on standardized evaluation infrastructure [Direction 1] and direct method comparisons [Directions 3,6] to resolve existing contradictions, while medium-term work should explore heterogeneity dimensions [Direction 4], scale thresholds [Direction 5], and human interpretability at complexity [Direction 8]. Long-term investments in evolutionary communication at scale [Direction 9] and cross-domain compositional transfer [Direction 11] will determine whether emergent communication can achieve natural language's flexibility or remains task-specific. The field is poised to transition from exploratory demonstrations to systematic science if the recommended evaluation standards and comparative frameworks are adopted.