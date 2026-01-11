# bball Analysis Writing Standards

**Date**: January 27, 2025  
**Status**: Active Standards  
**Purpose**: Standards for writing analysis documents for the `bball` NBA raw data warehouse (PostgreSQL + SQL migrations + Python scripts).

## Analysis Document Structure

### Document Organization

In this repo, analysis and sprint docs live under `cursor-files/` with date-based folder structure:

```
cursor-files/
├── templates/
│   ├── ANALYSIS_STANDARDS.md
│   ├── ANALYSIS_TEMPLATE.md
│   ├── SPRINT_STANDARDS.md
│   └── SPRINT_TEMPLATE.md
├── analysis/
│   └── YYYY-MM-DD-[description]/
│       └── [filename].md
├── sprints/
│   └── YYYY-MM-DD-[description]/
│       └── sprint-[nn].md
└── summaries/
    └── <topic>_summary.md
```

### File Naming and Versioning (bball)

Use date-based folder structure with descriptive folder names. Each analysis/sprint gets its own dated folder.

**Date Verification**: Always use the `date` command to get the current date and time.

**Date Field Format**: The `**Date**:` field at the top of analysis/sprint documents should use the full `date` command output (includes time), e.g., "Sun Jan  4 20:11:19 PST 2026".

**Folder Name Format**: Extract the date portion and format as `YYYY-MM-DD` for folder names (e.g., "2026-01-04" from the date command output).

- **Analysis docs**: `cursor-files/analysis/YYYY-MM-DD-[description]/[filename].md`
  - Examples:
    - `cursor-files/analysis/2026-01-04-sprint-14-signal-improvement-integration/sprint_14_analysis.md`
    - `cursor-files/analysis/2025-12-30-signal-improvement-next-steps/signal_improvement_next_steps_analysis.md`
- **Sprint plans**: `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`
  - Example: `cursor-files/sprints/2025-12-30-signal-improvement-foundation/sprint-13-signal-improvement-foundation.md`

### Run Context (Time, Environment, and Snapshot Identity)

For `bball`, the most important “date” is the **data snapshot / ingestion run** being analyzed.

When an analysis depends on a specific snapshot, record:
- **Timestamp standard**: UTC
- **DB connection**: `DATABASE_URL` (from `.env`, example in `env.example`)
- **Raw artifacts**: exact paths under `data/raw/...`
- **DB identity**: `source_file_id` / `ingest_run_id` (if applicable)

Helpful evidence commands:

```bash
date -u
docker compose ps
source .env
python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations --dry-run
```

### Analysis Document Format

Each analysis document follows this structure:

1. **Executive Summary**: High-level overview and key findings
2. **Problem Statement**: Clear definition of the issue or opportunity
3. **Current State Analysis**: Detailed examination of existing code
4. **Technical Assessment**: Code quality, architecture, and performance analysis
5. **Recommendations**: Specific actionable improvements
6. **Implementation Plan**: Step-by-step approach to address issues
7. **Risk Assessment**: Potential challenges and mitigation strategies

### Document Naming Conventions

### Analysis Documents
- **Format**: `cursor-files/analysis/YYYY-MM-DD-[description]/[filename].md`
- **Examples**:
  - `cursor-files/analysis/2026-01-04-sprint-14-signal-improvement-integration/sprint_14_analysis.md`
  - `cursor-files/analysis/2025-12-30-signal-improvement-next-steps/signal_improvement_next_steps_analysis.md`


### Directory Naming

**Date-Based Folder Structure**: Create date-based folders for each analysis/sprint.

**Format**: `YYYY-MM-DD-[description]`
- **YYYY-MM-DD**: Extract date portion from `date` command output and format as `YYYY-MM-DD` (e.g., "Sun Jan  4 20:11:19 PST 2026" → "2026-01-04")
- **Description**: Brief kebab-case description (e.g., `sprint-14-signal-improvement-integration`)

**Note**: The `**Date**:` field at the top of documents uses the full `date` command output (with time), but folder names use only the date portion in `YYYY-MM-DD` format.

**Examples**:
- `cursor-files/analysis/2026-01-04-sprint-14-signal-improvement-integration/`
- `cursor-files/sprints/2025-12-30-signal-improvement-foundation/`

**File Naming Inside Folder**:
- Analysis files: Use descriptive names (e.g., `sprint_14_analysis.md`, `signal_improvement_analysis.md`)
- Sprint files: Use `sprint-[nn].md` format (e.g., `sprint-13-signal-improvement-foundation.md`)

## Analysis Evidence Requirements

### Concrete Proof and Evidence

**Concrete Proof and Evidence**: Every analysis statement must be backed by:
- **Code References**: Specific file paths, line numbers, and code snippets
- **Performance Metrics**: Measurable data supporting performance claims
- **Test Results**: Actual test output and coverage reports
- **Architecture Diagrams**: Visual representations of system components
- **Database Queries**: Actual queries and their execution plans
- **Error Logs**: Real error messages and stack traces
- **Configuration Examples**: Actual configuration files and settings

**Evidence Standards**:
- No claims without supporting evidence
- All metrics must be reproducible
- All code references must be exact
- All performance claims must be measurable
- All architectural statements must be verifiable



### Design Pattern Analysis (Important for relevant components)

**Every design pattern analysis MUST include**:

**A. Pattern Identification**:
- **Pattern Name**: Exact pattern name (e.g., "Repository Pattern", "Factory Pattern")
- **Pattern Category**: Architectural, Creational, Structural, or Behavioral
- **Pattern Intent**: Why this specific pattern is currently used or why it's relevant to the problem

**B. Implementation Analysis**:
- **Current Implementation**: How the pattern is currently implemented in the specific context
- **Code References**: Specific file paths, line numbers, and code snippets
- **Integration Points**: How the pattern integrates with other system components

**C. Benefits and Trade-offs**:
- **Benefits**: Specific advantages gained from its current use
- **Trade-offs**: Specific disadvantages or limitations of its current use
- **Quantified Impact**: Measurable benefits and costs where possible

**Example Format**:
```markdown
### Design Pattern Analysis: Repository Pattern

**Pattern Name**: Repository Pattern
**Pattern Category**: Structural
**Pattern Intent**: Provides a uniform interface for data access, abstracting database operations

**Implementation**:
- File: `src/modules/users/repository.py:15-45`
- Code: [Specific implementation details]
- Integration: Used by UserService for all database operations

**Benefits**:
- Provides uniform data access interface
- Enables easy testing with mock repositories
- Centralizes data access logic

**Trade-offs**:
- Adds abstraction layer complexity
- Requires additional interface definitions
- May introduce performance overhead
```

### Algorithm Analysis (Important for performance-critical components)

**Every algorithm analysis MUST include**:

**A. Algorithm Identification**:
- **Algorithm Name**: Exact algorithm name (e.g., "Binary Search", "Quick Sort")
- **Algorithm Type**: Search, Sort, Graph, Dynamic Programming, etc.
- **Big O Notation**: Time and space complexity analysis

**B. Implementation Analysis**:
- **Current Implementation**: How the algorithm is currently implemented
- **Use Case**: Why this specific algorithm was chosen for its current application
- **Performance Characteristics**: Detailed performance analysis

**C. Performance Analysis**:
- **Best Case**: O(?) - specific scenario
- **Average Case**: O(?) - typical scenario
- **Worst Case**: O(?) - worst scenario
- **Memory Usage**: Space requirements

**Example Format**:
```markdown
### Algorithm Analysis: Binary Search

**Algorithm Name**: Binary Search
**Algorithm Type**: Search Algorithm
**Big O Notation**: 
- Time Complexity: O(log n)
- Space Complexity: O(1)

**Implementation**:
- File: `src/utils/search.py:25-40`
- Use Case: Searching sorted user data for authentication
- Performance: Provides logarithmic time complexity for large datasets

**Performance Characteristics**:
- Best Case: O(1) - target found at middle
- Average Case: O(log n) - typical search scenario
- Worst Case: O(log n) - target not found
- Memory Usage: O(1) - constant space usage

**Why This Algorithm**: 
- Provides logarithmic time complexity for large datasets
- Essential for maintaining sub-second authentication response times
- Scales well as user base grows
```

### Design Decision Analysis (Critical)

**Every design decision MUST include**:

**A. Problem Statement**:
- Clear description of the problem being solved
- Context and constraints
- Success criteria
- **Project Scope Consideration**: How the solution fits within the overall project size and complexity

**A.1. Sprint Scope Analysis (Critical)**:
- **Complexity Assessment**: Analyze the complexity of the problem and solution
- **Sprint Scope Determination**: Determine whether one or multiple sprints are needed
- **Scope Justification**: Provide clear reasoning for sprint scope decisions
- **Timeline Considerations**: Assess realistic implementation timeline based on complexity

**Sprint Scope Analysis Requirements**:
- **Single Sprint Indicators**: Problems that can be solved in 1-2 weeks with 1-3 developers
- **Multiple Sprint Indicators**: Problems requiring 3+ weeks, multiple teams, or complex dependencies
- **Complexity Metrics**: Use quantitative measures (lines of code, files affected, dependencies)
- **Risk Assessment**: Evaluate implementation risks that might affect sprint scope
- **Resource Requirements**: Assess team capacity and availability for sprint execution

**Example Sprint Scope Analysis Format**:
```markdown
### Sprint Scope Analysis: Database Migration

**Complexity Assessment**:
- **Files Affected**: 45 files across 8 modules
- **Lines of Code**: ~2,500 lines to be modified
- **Dependencies**: 12 external libraries, 3 database schemas
- **Team Impact**: 3 developers, 1 database administrator

**Sprint Scope Determination**: Multiple Sprints Required

**Scope Justification**:
- **Sprint 1**: Schema migration and core data transfer (2 weeks)
- **Sprint 2**: Application layer updates and testing (2 weeks)
- **Sprint 3**: Performance optimization and monitoring (1 week)

**Timeline Considerations**:
- **Total Duration**: 5 weeks across 3 sprints
- **Critical Path**: Database schema changes must complete before application updates
- **Risk Factors**: Data integrity, downtime minimization, rollback complexity

**Single Sprint Alternative**: Not viable due to:
- High risk of data loss with compressed timeline
- Insufficient testing time for critical data migration
- Team capacity constraints for parallel development
```

**B. Multiple Solution Analysis (Critical)**:
- **Minimum 3 different approaches** must be considered and analyzed
- Each solution must include:
  - **Design Pattern Name**: Exact pattern used (e.g., "Repository Pattern", "Factory Pattern")
  - **Algorithm Analysis**: If applicable, include Big O notation for any algorithms
  - **Implementation Complexity**: Detailed assessment of implementation effort
  - **Maintenance Overhead**: Long-term maintenance requirements
  - **Scalability Considerations**: How solution scales with project growth

**C. Cost-Benefit Analysis (Critical)**:
- **Implementation Cost**: Development time, complexity, learning curve
- **Maintenance Cost**: Ongoing support, debugging, updates
- **Performance Benefit**: Quantified performance improvements
- **Maintainability Benefit**: Code quality and developer productivity improvements
- **Risk Cost**: Potential issues and their impact
- **Over-Engineering Prevention**: Assessment of whether solution complexity matches problem complexity

**D. Solution Selection Criteria**:
- **Project Size Appropriateness**: Solution complexity matches project scope
- **Team Capability**: Solution matches team's current skill level
- **Timeline Constraints**: Solution fits within project timeline
- **Future Growth**: Solution accommodates expected project evolution
- **Technical Debt**: Solution reduces rather than increases technical debt

**E. Pros and Cons Analysis**:
- **Pros**: Specific advantages with quantified benefits
- **Cons**: Specific disadvantages with quantified costs
- **Risk Assessment**: Potential issues and mitigation strategies
- **Trade-off Analysis**: What was sacrificed for what was gained
- **Over-Engineering Risk**: Assessment of solution complexity vs. problem complexity

**Example Format**:
```markdown
### Design Decision: Database Connection Pooling

**Problem Statement**:
- High concurrent user load causing database connection exhaustion
- Connection creation overhead impacting response times
- Need to support 1000+ concurrent users
- **Project Scope**: Medium-sized application with 10-50 developers, expected to grow 3x in next 2 years

**Multiple Solution Analysis**:

**Option 1: Single Connection per Request**
- **Design Pattern**: None (Direct Connection Pattern)
- **Algorithm**: O(n) connection creation per request
- **Implementation Complexity**: Low (2-4 hours)
- **Maintenance Overhead**: Low (minimal configuration)
- **Scalability**: Poor (max 100 concurrent users)
- **Cost-Benefit**: Low cost, very low benefit
- **Over-Engineering Risk**: None (under-engineered)

**Option 2: Persistent Connections**
- **Design Pattern**: Singleton Pattern for connection management
- **Algorithm**: O(1) connection access, O(n) memory growth
- **Implementation Complexity**: Medium (8-12 hours)
- **Maintenance Overhead**: High (connection leak monitoring)
- **Scalability**: Poor (memory grows linearly)
- **Cost-Benefit**: Medium cost, low benefit
- **Over-Engineering Risk**: Low (simple but problematic)

**Option 3: Connection Pooling (CHOSEN)**
- **Design Pattern**: Object Pool Pattern
- **Algorithm**: O(1) connection acquisition, O(1) memory usage
- **Implementation Complexity**: Medium (12-16 hours)
- **Maintenance Overhead**: Medium (configuration tuning)
- **Scalability**: Excellent (supports 1000+ users)
- **Cost-Benefit**: Medium cost, high benefit
- **Over-Engineering Risk**: Low (appropriate complexity for problem)

**Cost-Benefit Analysis**:

**Implementation Cost**:
- **Development Time**: 12-16 hours (medium complexity)
- **Learning Curve**: 2-4 hours (team familiar with pooling concepts)
- **Configuration Effort**: 4-6 hours (pool sizing and tuning)

**Maintenance Cost**:
- **Monitoring**: 1-2 hours/month (connection health checks)
- **Tuning**: 2-4 hours/quarter (performance optimization)
- **Debugging**: 2-3 hours/incident (connection issues)

**Performance Benefit**:
- **Response Time**: 95% improvement (50ms → 2ms connection creation)
- **Throughput**: 10x improvement (100 → 1000+ concurrent users)
- **Resource Efficiency**: Constant memory usage vs. linear growth

**Maintainability Benefit**:
- **Code Quality**: Centralized connection management
- **Developer Productivity**: Reduced connection-related bugs
- **System Reliability**: Automatic connection health management

**Risk Cost**:
- **Pool Exhaustion**: Medium risk, mitigated by monitoring
- **Configuration Errors**: Low risk, mitigated by documentation
- **Memory Leaks**: Low risk, mitigated by automatic cleanup

**Over-Engineering Prevention**:
- **Problem Complexity**: High (concurrent user management)
- **Solution Complexity**: Medium (pool management)
- **Appropriateness**: Solution complexity matches problem complexity
- **Future Growth**: Accommodates 3x growth without changes

**Solution Selection Criteria**:
- **Project Size Appropriateness**: ✅ Medium complexity for medium project
- **Team Capability**: ✅ Team has pooling experience
- **Timeline Constraints**: ✅ Fits within 2-week sprint
- **Future Growth**: ✅ Supports 3x user growth
- **Technical Debt**: ✅ Reduces connection-related technical debt

**Pros and Cons Analysis**:

**Pros**:
- **Performance**: 95% reduction in connection creation time (50ms → 2ms)
- **Scalability**: Supports 1000+ concurrent users vs 100 without pooling
- **Resource Efficiency**: Constant memory usage regardless of user count
- **Reliability**: Automatic connection health checks and recovery
- **Maintainability**: Centralized connection management reduces bugs

**Cons**:
- **Complexity**: Additional configuration and monitoring required
- **Memory Overhead**: 20-100 connections consume ~50-250MB RAM
- **Configuration Sensitivity**: Pool size must be tuned for optimal performance
- **Debugging Difficulty**: Connection issues may be harder to trace
- **Learning Curve**: Team needs to understand pooling concepts

**Risk Assessment**:
- **Pool Exhaustion**: Mitigated by monitoring and alerting
- **Connection Leaks**: Mitigated by automatic cleanup and health checks
- **Performance Degradation**: Mitigated by connection recycling
- **Configuration Errors**: Mitigated by comprehensive documentation

**Trade-off Analysis**:
- **Sacrificed**: Simplicity and ease of debugging
- **Gained**: Scalability, performance, and resource efficiency
- **Net Benefit**: 10x improvement in concurrent user capacity
- **Over-Engineering Risk**: Low (solution complexity appropriate for problem)
```

### Performance Analysis (Important for performance-critical components)

**Every performance-critical component MUST include**:
- **Baseline Metrics**: Current performance measurements
- **Target Metrics**: Desired performance goals
- **Bottleneck Analysis**: Identification of performance bottlenecks
- **Optimization Strategy**: Specific optimization techniques to be used
- **Performance Testing**: How performance will be tested and benchmarked
- **Monitoring Strategy**: How performance will be monitored in production

### Security Analysis (Important for security-related components)

**Every security-related component MUST include**:
- **Threat Model**: Specific threats being addressed
- **Security Controls**: Specific security measures implemented
- **Vulnerability Assessment**: Potential security vulnerabilities
- **Attack Surface Analysis**: How the component affects exposed attack vectors
- **Security Testing**: Penetration testing and security validation planned

### Error Analysis (Critical for error-fixing or troubleshooting analyses)

**Every analysis that addresses fixing errors, bugs, or system failures MUST include**:

### **Root Cause Analysis (Critical)**:
- **Primary Cause**: The fundamental reason why the error occurred
- **Contributing Factors**: Secondary factors that enabled or exacerbated the error
- **Timeline Analysis**: When the error was introduced and how long it persisted
- **Impact Assessment**: What systems, users, or processes were affected by the error

### **Error Classification**:
- **Error Type**: Technical classification (e.g., "NullPointerException", "Database Connection Timeout", "Configuration Error")
- **Severity Level**: Critical/High/Medium/Low with business impact justification
- **Frequency**: How often the error occurs (single occurrence, intermittent, constant)
- **Reproducibility**: Steps to reproduce the error consistently

### **System State Analysis**:
- **Pre-Error State**: System configuration and state before the error occurred
- **Error Trigger**: Specific conditions, inputs, or events that caused the error
- **Post-Error State**: System state after the error occurred
- **Error Propagation**: How the error spread through the system

### **Evidence Collection**:
- **Error Messages**: Exact error messages with timestamps and context
- **Stack Traces**: Complete stack traces with file paths and line numbers
- **Log Entries**: Relevant log entries before, during, and after the error
- **System Metrics**: Performance metrics, memory usage, CPU usage during error
- **User Reports**: User-reported symptoms and impact descriptions

### **Why This Error Occurred**:
- **Design Flaw**: Fundamental design issues that made the error possible
- **Implementation Bug**: Specific coding errors or logic mistakes
- **Configuration Error**: Incorrect settings, environment variables, or dependencies
- **Resource Constraint**: Insufficient resources (memory, disk space, network bandwidth)
- **External Dependency**: Issues with third-party services, APIs, or libraries
- **Human Error**: Mistakes in deployment, configuration, or maintenance
- **Environmental Factors**: Infrastructure issues, network problems, or hardware failures

### **Prevention Analysis**:
- **Early Warning Signs**: Indicators that could have detected the error earlier
- **Missing Safeguards**: Protective measures that should have been in place
- **Testing Gaps**: Test scenarios that would have caught this error
- **Monitoring Blind Spots**: Metrics or alerts that should have been configured
- **Process Failures**: Development, deployment, or operational processes that failed

### **Example Error Analysis Format**:
```markdown
### Error Analysis: Database Connection Pool Exhaustion

**Error Classification**:
- **Error Type**: Resource Exhaustion
- **Severity Level**: High (caused complete system unavailability)
- **Frequency**: Intermittent (occurred 3 times over 2 days)
- **Reproducibility**: Reproducible under high load conditions

**Root Cause Analysis**:
- **Primary Cause**: Connection pool size configured too small for actual load
- **Contributing Factors**: 
  - No connection leak detection
  - Inadequate monitoring of connection usage
  - Missing connection timeout configuration
- **Timeline Analysis**: Error introduced during last deployment when connection pool size was reduced from 50 to 10
- **Impact Assessment**: 100% of users unable to access system for 15-30 minutes per occurrence

**System State Analysis**:
- **Pre-Error State**: System running normally with 8-12 active connections
- **Error Trigger**: Sudden traffic spike to 25+ concurrent users
- **Post-Error State**: All connection pool slots exhausted, new requests queued indefinitely
- **Error Propagation**: Frontend became unresponsive, API calls timed out, user sessions lost

**Evidence Collection**:
- **Error Messages**: "FATAL: sorry, too many clients already" (PostgreSQL error)
- **Stack Traces**: Connection pool acquisition timeout in database service layer
- **Log Entries**: Connection pool metrics showing 0 available connections
- **System Metrics**: CPU usage normal, memory usage stable, network latency normal
- **User Reports**: "Application not loading", "Login button not working"

**Why This Error Occurred**:
- **Configuration Error**: Connection pool size reduced from 50 to 10 without load testing
- **Design Flaw**: No graceful degradation when connection pool exhausted
- **Missing Safeguards**: No connection leak detection or automatic pool expansion
- **Testing Gap**: Load testing not performed after configuration change
- **Monitoring Blind Spot**: Connection pool utilization not monitored or alerted

**Prevention Analysis**:
- **Early Warning Signs**: Gradual increase in connection pool utilization over time
- **Missing Safeguards**: Connection leak detection, pool size auto-scaling, circuit breakers
- **Testing Gaps**: Load testing with realistic user scenarios
- **Monitoring Blind Spots**: Connection pool metrics, connection duration tracking
- **Process Failures**: Configuration changes not validated through testing pipeline
```

## 📐 Document Quality Standards

### **Emphasis Hierarchy System**

**Clear priority levels for requirements and guidelines:**

- **Critical**: Must be followed - failure results in invalid analysis
- **Important**: Should be followed - improves analysis quality significantly  
- **Recommended**: Best practice - enhances analysis completeness

### **Zero Ambiguity and Evidence-Based Analysis**

**Every section of every document MUST be extremely clear, specific, concise, explicit, and leave absolutely no room for confusion or interpretation.**

**Evidence-Based Analysis Standards**:
- **NO ASSUMPTIONS**: Never make assumptions about reader knowledge, system behavior, or implementation details
- **NO VAGUE LANGUAGE**: Avoid words like "likely", "probably", "mostly", "generally", "typically", "usually", "about", "approximately", "seems", "appears", "might", "could", "should"
- **NO APPROXIMATIONS**: Use exact measurements, not "about" or "approximately"
- **PERFECT COMPLETENESS**: Every analysis must be 100% complete, not "mostly complete"
- **CONCRETE EVIDENCE**: Every claim must be backed by specific, verifiable evidence
- **EXACT SPECIFICATIONS**: Use precise technical terms and exact specifications
- **FILE VERIFICATION**: Always check actual file contents before making any claims
- **COMMAND EVIDENCE**: Include exact commands used and their verbatim output
- **HONEST ASSESSMENT**: Report actual findings, not assumptions or expectations
- **NO GIT USAGE**: Do not direct anyone to use git unless explicitly mentioned in the prompt by the prompter that git can be used

### **Evidence-Based Analysis Requirements**

### **File Content Verification**
**Critical**: Before making ANY claim about code, configuration, or system state, you must:

1. **Read Actual File Contents**: Use `read_file` tool to examine exact file contents
2. **Run Verification Commands**: Execute specific commands to gather data
3. **Document Command Output**: Include exact command and verbatim response
4. **Verify Claims**: Cross-reference all statements with actual evidence

### **Evidence Documentation Format**
**Every claim MUST include:**

```markdown
**Evidence**: 
- **Command**: `[exact command executed]`
- **Output**: 
  ```
  [verbatim command output]
  ```
- **File**: `path/to/file.ext:line-range`
- **Content**: 
  ```[language]
  [exact code snippet]
  ```
```

### **Forbidden Practices**
- **NEVER** make claims without verifying file contents
- **NEVER** assume system behavior without testing
- **NEVER** use vague language like "likely" or "probably"
- **NEVER** approximate measurements or counts
- **NEVER** report "mostly complete" - strive for 100% completion
- **NEVER** direct anyone to use git unless explicitly mentioned in the prompt by the prompter that git can be used

### **DATE VERIFICATION REQUIREMENTS**
For `bball`, the most important time context is the **data snapshot** (raw files) and the **ingestion run identity** (DB).

- **MANDATORY**: Record UTC time and the exact artifacts being analyzed.
- **MANDATORY**: Use `date -u` for timestamps included in docs.
- **FORBIDDEN**: Use file modification time as a proxy for the snapshot time.

```bash
date -u
source .env
echo "$DATABASE_URL"
```

### **Database Access Setup**
This repo uses **PostgreSQL** (typically via Docker Compose) and a single connection env var:

- **Connection**: `DATABASE_URL` (stored in `.env`, example in `env.example`)

**Critical**: Verify DB connection before making database claims.  
**Critical Warnings**:
- **DO NOT modify database** (INSERT/UPDATE/ALTER/TRUNCATE/DELETE) unless the sprint explicitly requires it

Recommended local setup:

```bash
docker compose up -d db
docker compose ps
cp env.example .env
source .env
python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations
```

### **Database Verification Commands**

#### **PostgreSQL Verification Commands**:
```bash
source .env
./scripts/psql.sh
```

One-shot examples:

```bash
source .env
psql "$DATABASE_URL" -c "\dt"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM pbp_events;"
```

### **Error Analysis Requirements**
- **Critical**: If analyzing errors, bugs, or failures, include complete root cause analysis
- **SECTION REQUIRED**: "Why This Error Occurred" section with:
  - **Primary Cause**: The fundamental reason why the error occurred
  - **Contributing Factors**: Secondary factors that enabled or worsened the error
  - **Timeline**: When the error was introduced and when it manifested
  - **Impact Analysis**: What systems/processes were affected
  - **Prevention Strategy**: How to prevent similar errors in the future

### **Required Verification Steps**
1. **File Existence**: Verify files exist at claimed paths
2. **Content Accuracy**: Verify claimed content matches actual content
3. **Command Execution**: Verify commands work as documented
4. **Output Validation**: Verify expected outputs match actual outputs
5. **Cross-Reference**: Verify claims against multiple sources

### **Database Evidence Documentation Format**

#### **PostgreSQL Evidence Format**:
```markdown
**Database Evidence**: 
- **Command**: `source .env && psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM pbp_events;"`
- **Output**: 
  ```
  [verbatim command output]
  ```
- **Table**: `pbp_events`
- **Query**: `SELECT COUNT(*) FROM pbp_events;`
- **Result**: [describe the result precisely]
```

### **Clarity Requirements**

### **Language Standards**
- **Specific Terms**: Use exact technical terms, not generic descriptions
- **Complete Sentences**: Every instruction must be a complete, actionable sentence
- **Active Voice**: Use active voice for all instructions and descriptions
- **Present Tense**: Use present tense for current states, future tense for planned changes
- **Precise Quantification**: Use exact numbers, not approximations
- **FORBIDDEN WORDS**: Never use "likely", "probably", "mostly", "generally", "typically", "usually", "about", "approximately", "seems", "appears", "might", "could", "should"
- **REQUIRED PRECISION**: Use definitive language: "is", "will", "does", "has", "contains", "requires", "implements"
- **CONCRETE STATEMENTS**: Every statement must be factual and verifiable, not speculative

### **Technical Precision**
- **Exact Paths**: Always use complete file paths from project root
- **Complete Commands**: Include all flags, parameters, and options
- **Specific Versions**: Reference exact version numbers, not ranges
- **Full Configuration**: Show complete configuration blocks, not snippets
- **Concrete Examples**: Provide actual examples, not placeholders

### **Content Validation Checklist**

Before finalizing any document, verify it meets these requirements:

### **Technical Accuracy**
- [ ] All file paths are correct and complete
- [ ] All commands are tested and work as documented
- [ ] All code examples are syntactically correct
- [ ] All configuration values are valid
- [ ] All dependencies are listed with correct versions

### **Completeness**
- [ ] No steps are skipped or assumed
- [ ] All prerequisites are explicitly stated
- [ ] All expected outputs are defined
- [ ] All potential errors are addressed
- [ ] All file modifications are documented

### **Clarity**
- [ ] Any developer can follow instructions without questions
- [ ] No ambiguous language or terms
- [ ] No assumptions about reader knowledge
- [ ] All technical terms are used consistently
- [ ] All examples are complete and realistic

### **Validation Checklist**

**Before finalizing any analysis, verify**:
- [ ] **File Verification**: All file contents verified using `read_file` tool before making claims
- [ ] **Command Evidence**: All data gathering commands documented with exact commands and verbatim output
- [ ] **Date Verification**: Used `date` command to verify today's date (not file timestamps)
- [ ] **Database Verification**: Verified database access and contents before making database claims
- [ ] **Problem Complexity Assessment**: Comprehensive complexity analysis included with sprint scope recommendation
- [ ] **No Assumptions**: No assumptions made about reader knowledge, system behavior, or implementation details
- [ ] **No Vague Language**: No use of "likely", "probably", "mostly", "generally", "typically", "usually", "about", "approximately", "seems", "appears", "might", "could", "should"
- [ ] **Definitive Language**: All statements use definitive language ("is", "will", "does", "has", "contains", "requires", "implements")
- [ ] **Concrete Evidence**: Every claim backed by specific, verifiable evidence
- [ ] **Perfect Completeness**: Analysis is 100% complete, not "mostly complete"
- [ ] **Honest Assessment**: Actual findings reported, not assumptions or expectations
- [ ] **Design Pattern**: Specific pattern name and implementation details provided
- [ ] **Algorithm**: Algorithm name, Big O notation, and performance characteristics specified
- [ ] **Multiple Solutions**: At least 3 different approaches considered and analyzed
- [ ] **Cost-Benefit Analysis**: Implementation cost, maintenance cost, and benefits quantified
- [ ] **Project Scope Consideration**: Solution complexity matches project size and scope
- [ ] **Over-Engineering Prevention**: Assessment of solution complexity vs. problem complexity
- [ ] **Pros and Cons**: Detailed analysis of advantages and disadvantages provided
- [ ] **Performance Analysis**: Baseline, target, and actual performance metrics included
- [ ] **Security Analysis**: Threat model and security controls documented
- [ ] **Error Analysis**: If analyzing errors/bugs/failures, complete root cause analysis with "Why This Error Occurred" section
- [ ] **Evidence**: All claims supported by concrete evidence and measurements
- [ ] **Alternatives**: At least 3 alternative approaches considered and analyzed
- [ ] **Trade-offs**: Clear explanation of what was sacrificed for what was gained
- [ ] **Future Impact**: Analysis of how decisions will affect future development
- [ ] **Maintenance**: Long-term maintenance and support implications documented
- [ ] **Team Capability**: Solution matches team's current skill level
- [ ] **Timeline Appropriateness**: Solution fits within project timeline constraints

## 📋 File Organization Rules & Naming Standards

### **File Organization Principles**

### **Hierarchical Organization**
- **Primary**: By document type (analyses, sprints, standards)
- **Secondary**: By date (chronological ordering)
- **Tertiary**: By functional area (modules, features, components)

### **Temporal Organization**
- **Active Work**: Current analyses and sprints in progress
- **Completed Work**: Archived analyses and completed sprints
- **Reference Materials**: Standards, templates, and guidelines

### **Functional Organization**
- **Module-Specific**: Documentation grouped by system modules
- **Cross-Cutting**: Documentation that spans multiple modules
- **Infrastructure**: Deployment, configuration, and operational documentation

### **File Naming Standards**

### **Analysis Documents**
- **Format**: `cursor-files/analysis/<topic>_analysis_v{n}.md`
- **Examples**:
  - `cursor-files/analysis/nba_data_sources_analysis_v2.md`
  - `cursor-files/analysis/nba_pbp_postgres_schema_analysis.md`


### **Standards Documents**
- **Format**: `descriptive_name_standards.md`
- **Examples**:
  - `coding_standards.md`
  - `api_design_standards.md`

### **Directory Structure Standards**

### **Analysis Directory Structure**
```
cursor-files/
├── analysis/
│   └── YYYY-MM-DD-[description]/
│       └── [filename].md
├── sprints/
│   └── YYYY-MM-DD-[description]/
│       └── sprint-[nn].md
└── templates/
    ├── ANALYSIS_STANDARDS.md
    └── ANALYSIS_TEMPLATE.md
```

### **Document Placement Rule (bball)**

- Put analysis documents in `cursor-files/analysis/YYYY-MM-DD-[description]/[filename].md`.
- Put sprint plans in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`.
- Put templates under `cursor-files/templates/`.
- **Date Verification**: Always use `date` command to get current date, format as `YYYY-MM-DD`.

## 📖 Quick Navigation

### **Analysis Documentation**
- **Analysis Standards**: `cursor-files/templates/ANALYSIS_STANDARDS.md` (this document)
- **Analysis Template**: `cursor-files/templates/ANALYSIS_TEMPLATE.md` (analysis document template)

### **File Organization Help**
- **Analysis Standards**: `cursor-files/templates/ANALYSIS_STANDARDS.md` (this document)
- **Analysis Template**: `cursor-files/templates/ANALYSIS_TEMPLATE.md` (analysis document template)
- **File Placement Rules**: See "File Organization Rules" section above
- **Naming Standards**: See "File Naming Standards" section above
- **Run Context**: See "Run Context (Time, Environment, and Snapshot Identity)" section above
