# Analysis Template: [Analysis Title]

**Date**: [Use `date` command output, e.g., "Sun Jan  4 20:11:19 PST 2026"]  
**Status**: [Draft/In Review/Approved/Completed]  
**Author**: [Author Name]  
**Reviewers**: [Reviewer Names]  
**Version**: [v1.0]  
**Purpose**: [Brief description of what this analysis covers]

## Analysis Standards Reference

**Important**: This analysis must follow the comprehensive standards defined in `ANALYSIS_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based Analysis**: Every claim must be backed by concrete evidence (code refs, commands + verbatim output, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers analyzed.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: Use PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Write analyses in `cursor-files/analysis/YYYY-MM-DD-[description]/[filename].md` and sprints in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`. Always use `date` command to verify current date and format as `YYYY-MM-DD`.

**See `ANALYSIS_STANDARDS.md` for complete requirements and validation checklist.**

## Executive Summary

### Key Findings
- **[Finding 1]**: [Brief description with quantified impact]
- **[Finding 2]**: [Brief description with quantified impact]
- **[Finding 3]**: [Brief description with quantified impact]

### Critical Issues Identified
- **[Issue 1]**: [Description with severity level and impact]
- **[Issue 2]**: [Description with severity level and impact]

### Recommended Actions
- **[Action 1]**: [Priority: High/Medium/Low] - [Brief description]
- **[Action 2]**: [Priority: High/Medium/Low] - [Brief description]

### Success Metrics
- **[Metric 1]**: [Baseline] → [Target] ([% improvement])
- **[Metric 2]**: [Baseline] → [Target] ([% improvement])

## Problem Statement

### Current Situation
[Detailed description of the current state with specific technical details]

### Pain Points
- **[Pain Point 1]**: [Description with specific examples and impact]
- **[Pain Point 2]**: [Description with specific examples and impact]

### Business Impact
- **Performance Impact**: [Quantified metrics]
- **User Experience Impact**: [Specific user-facing issues]
- **Maintenance Impact**: [Developer productivity and technical debt]

### Success Criteria
- **[Criterion 1]**: [Measurable outcome]
- **[Criterion 2]**: [Measurable outcome]

### Problem Complexity Assessment

**Scope Analysis**:
- **Files Affected**: [Number of files and modules involved]
- **Estimated Effort**: [Hours with justification]
- **Technical Complexity**: [Assessment with specific challenges]
- **Risk Level**: [Risk assessment with mitigation strategies]

**Sprint Scope Recommendation**: [Single Sprint/Multiple Sprints/Epic-Level]
- **Rationale**: [Justification for sprint scope decision]
- **Recommended Approach**: [Sprint breakdown if multiple sprints]
  - Sprint 1: [Description and estimated effort]
  - Sprint 2: [Description and estimated effort]
  - Sprint 3: [Description and estimated effort]

**Dependency Analysis**:
- [Sprint dependencies and critical path]
- [Parallel work opportunities]
- [Risk mitigation strategies]

## Current State Analysis

### System Architecture Overview
[High-level architecture description with diagrams]

### Code Quality Assessment

### Complexity Analysis
- **Cyclomatic Complexity**: [Average/Max values with file references]
- **Cognitive Complexity**: [Average/Max values with file references]
- **Technical Debt Ratio**: [Percentage with specific debt items]

### Maintainability Metrics
- **Code Coverage**: [Percentage with specific uncovered areas]
- **Test Quality**: [Test coverage and quality assessment]
- **Documentation Coverage**: [API docs, inline comments, README completeness]

### Performance Baseline
- **Response Time**: [Current metrics with specific endpoints]
- **Memory Usage**: [Current consumption patterns]
- **Database Performance**: [Query performance and optimization opportunities]

### Security Assessment
- **Vulnerability Scan Results**: [Specific findings with severity levels]
- **Authentication/Authorization**: [Current implementation analysis]
- **Data Protection**: [Encryption and data handling practices]

### Dependencies Analysis
- **External Dependencies**: [List with versions and risk assessment]
- **Internal Dependencies**: [Module interdependencies and coupling]
- **Infrastructure Dependencies**: [Database, cache, external services]

## Technical Assessment

### Design Pattern Analysis

### Current Patterns in Use
```markdown
#### Design Pattern Analysis: [Pattern Name]

**Pattern Name**: [Exact pattern name]
**Pattern Category**: [Architectural/Creational/Structural/Behavioral]
**Pattern Intent**: [Why this pattern was chosen]

**Implementation**:
- [Specific implementation details with code references]
- [File: `path/to/file.ext:line-range`]

**Benefits**:
- [Specific advantages gained]
- [Quantified benefits where possible]

**Trade-offs**:
- [Specific disadvantages or limitations]
- [Quantified costs where possible]

**Why This Pattern**: [Rationale for pattern choice]
```

### Missing Patterns
- **[Missing Pattern 1]**: [Why it should be implemented]
- **[Missing Pattern 2]**: [Why it should be implemented]

### Algorithm Analysis

### Current Algorithms
```markdown
#### Algorithm Analysis: [Algorithm Name]

**Algorithm Name**: [Exact algorithm name]
**Algorithm Type**: [Search/Sort/Graph/Dynamic Programming/etc.]
**Big O Notation**: 
- Time Complexity: [O(n), O(log n), etc.]
- Space Complexity: [O(1), O(n), etc.]

**Algorithm Description**:
- [How the algorithm works]
- [Implementation details]

**Use Case**: 
- [Why this specific algorithm was chosen]
- [Performance requirements]

**Performance Characteristics**:
- Best Case: [O(?) - specific scenario]
- Average Case: [O(?) - typical scenario]
- Worst Case: [O(?) - worst scenario]
- Memory Usage: [Space requirements]

**Why This Algorithm**: 
- [Rationale for algorithm choice]
- [Performance benefits]
```

### Optimization Opportunities
- **[Algorithm 1]**: [Current complexity] → [Optimized complexity] ([% improvement])
- **[Algorithm 2]**: [Current complexity] → [Optimized complexity] ([% improvement])

### Performance Analysis

### Baseline Metrics
- **Response Time**: [Current measurements with specific endpoints]
- **Throughput**: [Requests per second]
- **Memory Usage**: [Peak and average consumption]
- **CPU Usage**: [Peak and average utilization]
- **Database Performance**: [Query execution times]

### Bottleneck Analysis
- **Primary Bottleneck**: [Specific bottleneck with file references]
- **Secondary Bottleneck**: [Specific bottleneck with file references]
- **Tertiary Bottleneck**: [Specific bottleneck with file references]

#### Performance Testing Results
- **Load Test**: [Results with specific metrics]
- **Stress Test**: [Results with breaking points]
- **Memory Test**: [Memory usage patterns and leaks]

### Security Analysis

#### Threat Model
- **Threat 1**: [Specific threat description]
- **Threat 2**: [Specific threat description]
- **Threat 3**: [Specific threat description]

#### Security Controls
- **Authentication**: [Current implementation with specific details]
- **Authorization**: [Current implementation with specific details]
- **Data Protection**: [Encryption and data handling]
- **Input Validation**: [Current validation mechanisms]

#### Vulnerability Assessment
- **High Risk**: [Specific vulnerabilities with mitigation]
- **Medium Risk**: [Specific vulnerabilities with mitigation]
- **Low Risk**: [Specific vulnerabilities with mitigation]

#### Attack Surface Analysis
- **API Endpoints**: [Exposed endpoints and protection]
- **Database**: [Database security measures]
- **External Integrations**: [Third-party security considerations]

### Error Analysis (MANDATORY for error-fixing or troubleshooting analyses)

#### Error Classification
- **Error Type**: [Technical classification - e.g., "NullPointerException", "Database Connection Timeout", "Configuration Error"]
- **Severity Level**: [Critical/High/Medium/Low with business impact justification]
- **Frequency**: [How often the error occurs - single occurrence, intermittent, constant]
- **Reproducibility**: [Steps to reproduce the error consistently]

#### Root Cause Analysis (MANDATORY)
- **Primary Cause**: [The fundamental reason why the error occurred]
- **Contributing Factors**: [Secondary factors that enabled or exacerbated the error]
  - [Contributing factor 1]
  - [Contributing factor 2]
  - [Contributing factor 3]
- **Timeline Analysis**: [When the error was introduced and how long it persisted]
- **Impact Assessment**: [What systems, users, or processes were affected by the error]

#### System State Analysis
- **Pre-Error State**: [System configuration and state before the error occurred]
- **Error Trigger**: [Specific conditions, inputs, or events that caused the error]
- **Post-Error State**: [System state after the error occurred]
- **Error Propagation**: [How the error spread through the system]

#### Evidence Collection
- **Error Messages**: [Exact error messages with timestamps and context]
  - **Command**: `[command that produced the error]`
  - **Output**: 
    ```
    [verbatim error message output]
    ```
- **Stack Traces**: [Complete stack traces with file paths and line numbers]
  - **File**: `path/to/file.ext:line-range`
  - **Content**: 
    ```[language]
    [exact code snippet where error occurred]
    ```
- **Log Entries**: [Relevant log entries before, during, and after the error]
  - **Command**: `grep "error_pattern" /path/to/logfile.log`
  - **Output**: 
    ```
    [verbatim log entries]
    ```
- **System Metrics**: [Performance metrics, memory usage, CPU usage during error]
  - **Command**: `[monitoring command used]`
  - **Output**: 
    ```
    [verbatim system metrics output]
    ```
- **User Reports**: [User-reported symptoms and impact descriptions]

#### Why This Error Occurred (MANDATORY ANALYSIS)
- **Design Flaw**: [Fundamental design issues that made the error possible]
- **Implementation Bug**: [Specific coding errors or logic mistakes]
  - **File**: `path/to/file.ext:line-range`
  - **Code**: 
    ```[language]
    [problematic code snippet]
    ```
  - **Issue**: [Specific problem with the code]
- **Configuration Error**: [Incorrect settings, environment variables, or dependencies]
  - **Configuration File**: `path/to/config.file`
  - **Incorrect Setting**: [specific setting that was wrong]
  - **Correct Setting**: [what the setting should have been]
- **Resource Constraint**: [Insufficient resources - memory, disk space, network bandwidth]
- **External Dependency**: [Issues with third-party services, APIs, or libraries]
- **Human Error**: [Mistakes in deployment, configuration, or maintenance]
- **Environmental Factors**: [Infrastructure issues, network problems, or hardware failures]

#### Prevention Analysis
- **Early Warning Signs**: [Indicators that could have detected the error earlier]
- **Missing Safeguards**: [Protective measures that should have been in place]
- **Testing Gaps**: [Test scenarios that would have caught this error]
- **Monitoring Blind Spots**: [Metrics or alerts that should have been configured]
- **Process Failures**: [Development, deployment, or operational processes that failed]

## Evidence and Proof

### MANDATORY: File Content Verification
**Before making ANY claim about code, configuration, or system state, you MUST:**

1. **Read Actual File Contents**: Use `read_file` tool to examine exact file contents
2. **Run Verification Commands**: Execute specific commands to gather data
3. **Document Command Output**: Include exact command and verbatim response
4. **Verify Claims**: Cross-reference all statements with actual evidence

### Database Evidence Template (PostgreSQL)
**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/ANALYSIS_STANDARDS.md`.

### Code References
- **File**: `path/to/file.ext:line-range`
  - **Issue**: [Specific problem description]
  - **Evidence**: 
    - **Command**: `[exact command executed]`
    - **Output**: 
      ```
      [verbatim command output]
      ```
    - **Content**: 
      ```[language]
      [exact code snippet]
      ```
  - **Impact**: [Quantified impact]

### Performance Metrics
- **Metric**: [Specific metric name]
  - **Current Value**: [Measured value]
  - **Target Value**: [Desired value]
  - **Measurement Method**: [How it was measured]
  - **Test Environment**: [Environment details]
  - **Evidence**:
    - **Command**: `[exact command executed]`
    - **Output**: 
      ```
      [verbatim command output]
      ```

### Test Results
- **Test Suite**: [Test name]
  - **Coverage**: [Percentage]
  - **Pass Rate**: [Percentage]
  - **Failed Tests**: [Specific failures with reasons]
  - **Evidence**:
    - **Command**: `[exact command executed]`
    - **Output**: 
      ```
      [verbatim command output]
      ```

### Benchmark Data
- **Benchmark**: [Benchmark name]
  - **Current Performance**: [Specific metrics]
  - **Industry Standard**: [Comparison data]
  - **Gap Analysis**: [Performance gap]
  - **Evidence**:
    - **Command**: `[exact command executed]`
    - **Output**: 
      ```
      [verbatim command output]
      ```

### Database Evidence

#### PostgreSQL Examples (bball)
- **Database Query**: [Specific query description]
  - **Command**: `source .env && psql "$DATABASE_URL" -c "[exact SQL query]"`
  - **Output**: 
    ```
    [verbatim query output]
    ```
  - **Table**: `[table_name]`
  - **Query**: `[exact SQL query]`
  - **Result**: [Specific findings from query]

- **Database Schema Verification**: [Schema verification description]
  - **Command**: `source .env && psql "$DATABASE_URL" -c "\d [table_name]"`
  - **Output**: 
    ```
    [verbatim schema output]
    ```
  - **Table**: `[table_name]`
  - **Schema**: [Specific schema findings]

## Recommendations

### Immediate Actions (Priority: High)
- **[Recommendation 1]**: [Specific action with implementation details]
  - **Files to Modify**: [Complete list with purposes]
  - **Estimated Effort**: [Hours/days]
  - **Risk Level**: [Low/Medium/High]
  - **Success Metrics**: [How to measure success]

### Short-term Improvements (Priority: Medium)
- **[Recommendation 2]**: [Specific action with implementation details]
  - **Files to Modify**: [Complete list with purposes]
  - **Estimated Effort**: [Hours/days]
  - **Risk Level**: [Low/Medium/High]
  - **Success Metrics**: [How to measure success]

### Long-term Strategic Changes (Priority: Low)
- **[Recommendation 3]**: [Specific action with implementation details]
  - **Files to Modify**: [Complete list with purposes]
  - **Estimated Effort**: [Hours/days]
  - **Risk Level**: [Low/Medium/High]
  - **Success Metrics**: [How to measure success]

### Design Decision Recommendations

#### Recommended Design Pattern: [Pattern Name]
```markdown
#### Design Decision: [Decision Title]

**Problem Statement**:
- [Clear description of the problem being solved]
- [Context and constraints]
- [Success criteria]
- **Project Scope**: [Project size, team size, expected growth, timeline constraints]

**Sprint Scope Analysis**:
- **Complexity Assessment**: [Files affected, lines of code, dependencies, team impact]
- **Sprint Scope Determination**: [Single Sprint / Multiple Sprints Required]
- **Scope Justification**: [Clear reasoning for sprint scope decisions with breakdown]
- **Timeline Considerations**: [Total duration, critical path, risk factors]
- **Single Sprint Alternative**: [Why single sprint is/is not viable]

**Multiple Solution Analysis**:

**Option 1: [Alternative Name]**
- **Design Pattern**: [Exact pattern name or "None" if no pattern]
- **Algorithm**: [Big O notation if applicable, e.g., "O(n) search", "O(1) lookup"]
- **Implementation Complexity**: [Low/Medium/High] ([X] hours)
- **Maintenance Overhead**: [Low/Medium/High] ([X] hours/month)
- **Scalability**: [Poor/Fair/Good/Excellent] ([specific metrics])
- **Cost-Benefit**: [Low/Medium/High] cost, [Low/Medium/High] benefit
- **Over-Engineering Risk**: [None/Low/Medium/High] ([reason])
- **Rejected**: [Why this alternative was rejected]

**Option 2: [Alternative Name]**
- **Design Pattern**: [Exact pattern name or "None" if no pattern]
- **Algorithm**: [Big O notation if applicable, e.g., "O(log n) search", "O(1) access"]
- **Implementation Complexity**: [Low/Medium/High] ([X] hours)
- **Maintenance Overhead**: [Low/Medium/High] ([X] hours/month)
- **Scalability**: [Poor/Fair/Good/Excellent] ([specific metrics])
- **Cost-Benefit**: [Low/Medium/High] cost, [Low/Medium/High] benefit
- **Over-Engineering Risk**: [None/Low/Medium/High] ([reason])
- **Rejected**: [Why this alternative was rejected]

**Option 3: [Chosen Alternative] (CHOSEN)**
- **Design Pattern**: [Exact pattern name]
- **Algorithm**: [Big O notation if applicable, e.g., "O(1) access", "O(log n) operations"]
- **Implementation Complexity**: [Low/Medium/High] ([X] hours)
- **Maintenance Overhead**: [Low/Medium/High] ([X] hours/month)
- **Scalability**: [Poor/Fair/Good/Excellent] ([specific metrics])
- **Cost-Benefit**: [Low/Medium/High] cost, [Low/Medium/High] benefit
- **Over-Engineering Risk**: [None/Low/Medium/High] ([reason])
- **Selected**: [Why this was chosen]

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: [X] hours ([complexity level])
- **Learning Curve**: [X] hours ([team skill assessment])
- **Configuration Effort**: [X] hours ([setup requirements])

**Maintenance Cost**:
- **Monitoring**: [X] hours/[time period] ([monitoring requirements])
- **Updates**: [X] hours/[time period] ([update frequency])
- **Debugging**: [X] hours/incident ([debugging complexity])

**Performance Benefit**:
- **Response Time**: [X]% improvement ([baseline] → [target])
- **Throughput**: [X]x improvement ([baseline] → [target])
- **Resource Efficiency**: [specific improvement metrics]

**Maintainability Benefit**:
- **Code Quality**: [specific improvements]
- **Developer Productivity**: [specific improvements]
- **System Reliability**: [specific improvements]

**Risk Cost**:
- **Risk 1**: [risk level] risk, mitigated by [mitigation strategy]
- **Risk 2**: [risk level] risk, mitigated by [mitigation strategy]

**Over-Engineering Prevention**:
- **Problem Complexity**: [Low/Medium/High] ([reason])
- **Solution Complexity**: [Low/Medium/High] ([reason])
- **Appropriateness**: [Solution complexity matches problem complexity]
- **Future Growth**: [How solution accommodates expected growth]

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅/❌ [reason]
- **Team Capability**: ✅/❌ [reason]
- **Timeline Constraints**: ✅/❌ [reason]
- **Future Growth**: ✅/❌ [reason]
- **Technical Debt**: ✅/❌ [reason]

**Chosen Solution**: [Detailed explanation]
- Implementation: [Specific technical implementation]
- Configuration: [Configuration details]
- Integration: [How it integrates with existing system]

**Pros and Cons Analysis**:

**Pros**:
- **Performance**: [Quantified performance benefits]
- **Maintainability**: [Specific maintainability improvements]
- **Scalability**: [Scalability benefits]
- **Reliability**: [Specific reliability improvements]

**Cons**:
- **Complexity**: [Specific complexity costs]
- **Learning Curve**: [Training requirements]
- **Migration Effort**: [Implementation effort]
- **Resource Usage**: [Specific resource costs]

**Risk Assessment**:
- **Risk 1**: [Specific risk with mitigation strategy]
- **Risk 2**: [Specific risk with mitigation strategy]
- **Risk 3**: [Specific risk with mitigation strategy]

**Trade-off Analysis**:
- **Sacrificed**: [What was sacrificed]
- **Gained**: [What was gained]
- **Net Benefit**: [Overall benefit assessment]
- **Over-Engineering Risk**: [Assessment of solution complexity vs. problem complexity]
```

## Implementation Plan

### Phase 1: Foundation (Duration: [X] hours)
**Objective**: [Specific technical objective]
**Dependencies**: [External dependencies, tools, setup]
**Deliverables**: [Concrete, testable deliverables]

#### Tasks
- **[Task 1]**: [Specific task description]
  - **Files**: [Files to modify/create]
  - **Effort**: [Hours]
  - **Prerequisites**: [Dependencies]

### Phase 2: Core Implementation (Duration: [X] hours)
**Objective**: [Specific technical objective building on Phase 1]
**Dependencies**: [Must complete Phase 1, plus additional dependencies]
**Deliverables**: [Concrete, testable deliverables]

#### Tasks
- **[Task 1]**: [Specific task description]
  - **Files**: [Files to modify/create]
  - **Effort**: [Hours]
  - **Prerequisites**: [Dependencies]

### Phase 3: Optimization and Testing (Duration: [X] hours)
**Objective**: [Specific technical objective completing main work]
**Dependencies**: [Must complete Phase 2, plus additional dependencies]
**Deliverables**: [Concrete, testable deliverables]

#### Tasks
- **[Task 1]**: [Specific task description]
  - **Files**: [Files to modify/create]
  - **Effort**: [Hours]
  - **Prerequisites**: [Dependencies]

### Phase 4: Documentation and Deployment (Duration: [X] hours)
**Objective**: [Documentation and deployment objectives]
**Dependencies**: [Must complete Phase 3]
**Deliverables**: [Documentation and deployment deliverables]

## Risk Assessment

### Technical Risks
- **Risk 1**: [Specific technical risk]
  - **Probability**: [High/Medium/Low]
  - **Impact**: [High/Medium/Low]
  - **Mitigation**: [Specific mitigation strategy]
  - **Contingency**: [Backup plan]

### Business Risks
- **Risk 1**: [Specific business risk]
  - **Probability**: [High/Medium/Low]
  - **Impact**: [High/Medium/Low]
  - **Mitigation**: [Specific mitigation strategy]
  - **Contingency**: [Backup plan]

### Resource Risks
- **Risk 1**: [Specific resource risk]
  - **Probability**: [High/Medium/Low]
  - **Impact**: [High/Medium/Low]
  - **Mitigation**: [Specific mitigation strategy]
  - **Contingency**: [Backup plan]

## Success Metrics and Monitoring

### Performance Metrics
- **Response Time**: [Target] ([% improvement from baseline])
- **Throughput**: [Target] ([% improvement from baseline])
- **Memory Usage**: [Target] ([% improvement from baseline])
- **Error Rate**: [Target] ([% improvement from baseline])

### Quality Metrics
- **Code Coverage**: [Target] ([% improvement from baseline])
- **Technical Debt**: [Target] ([% improvement from baseline])
- **Bug Rate**: [Target] ([% improvement from baseline])

### Business Metrics
- **User Satisfaction**: [Target] ([% improvement from baseline])
- **Development Velocity**: [Target] ([% improvement from baseline])
- **Maintenance Cost**: [Target] ([% improvement from baseline])

### Monitoring Strategy
- **Real-time Monitoring**: [Specific monitoring tools and metrics]
- **Alert Thresholds**: [Specific alert conditions]
- **Reporting**: [Reporting frequency and format]

## Appendices

### Appendix A: Code Samples
[Detailed code examples supporting the analysis]

### Appendix B: Performance Metrics
[Detailed performance data and benchmarks]

### Appendix C: Reference Materials
[Links to relevant documentation, standards, and resources]

### Appendix D: Glossary
[Technical terms and definitions used in the analysis]

---

## Document Validation

**IMPORTANT**: Use the comprehensive validation checklist in `ANALYSIS_STANDARDS.md` to ensure this analysis meets all quality standards.
