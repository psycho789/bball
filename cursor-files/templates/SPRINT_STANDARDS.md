# Sprint Writing Standards

**Date**: January 27, 2025  
**Status**: Active Standards  
**Purpose**: Comprehensive guidelines for writing sprint documentation

## Sprint Standards and Requirements

### Git Usage Restrictions

**Critical**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

**Git Usage Rules**:
- **NO git commands** unless explicitly mentioned in sprint plan
- **NO git operations** unless explicitly mentioned in analysis
- **NO version control** unless explicitly mentioned in prompt by prompter
- **NO commits, pushes, pulls, or branches** unless explicitly directed
- **NO git status, git log, or git diff** unless explicitly mentioned in sprint plan

**Exception**: Git usage is only allowed when:
1. Explicitly mentioned in the analysis document
2. Explicitly mentioned in the sprint plan
3. Explicitly mentioned in the prompt by the prompter that git can be used

### Post-Story Quality Assurance

**Critical Requirement**: After every sprint story completion, the project MUST:
- Validate the story via executable commands and record verbatim output
- Re-run DB migrations (dry-run or apply, as appropriate) when schema changes occur
- Re-run warehouse QC checks when data ingestion or derived views change

Repo-specific quality gates that exist today:
- `python scripts/migrate.py --dsn "$DATABASE_URL" --migrations-dir db/migrations --dry-run`
- `python scripts/qc_report.py --dsn "$DATABASE_URL" --game-id <GAME_ID> --out data/reports/qc_<GAME_ID>.json [--pbp-file data/raw/pbp/<GAME_ID>.json]`

### Story Requirements and Standards

Every sprint story must meet these technical requirements:

### 1. Technical Explicitness and Clarity
- **Developer-Ready**: Every story must be technically explicit, specific, and clear enough for any developer to understand without additional clarification
- **Implementation Details**: Include specific technical requirements, not just high-level descriptions
- **Context Provision**: Provide sufficient background and context for the implementation
- **Assumption Documentation**: Clearly state any assumptions or constraints

### 2. Working Examples and Documentation
- **Code Examples**: Provide relevant working code examples that demonstrate the expected implementation
- **API Examples**: Include request/response examples for API endpoints
- **Configuration Examples**: Show configuration files, environment variables, and setup requirements
- **Integration Examples**: Demonstrate how the feature integrates with existing systems

### 3. Pros and Cons Analysis
- **Technical Trade-offs**: Document the technical trade-offs of different implementation approaches
- **Performance Impact**: Analyze performance implications of the proposed solution
- **Maintenance Considerations**: Evaluate long-term maintenance and support requirements
- **Alternative Solutions**: Consider and document alternative approaches with their trade-offs

### 4. Definition of Done and Acceptance Criteria
Every story must include a comprehensive checklist:

**Technical Acceptance Criteria**:
- [ ] Migrations apply cleanly (or `--dry-run` output is captured) when DB schema changes occur
- [ ] Script entrypoints used in the story run successfully with required flags
- [ ] QC checks pass when the story affects ingestion, raw parsing, or derived views
- [ ] Documentation is updated and accurate
- [ ] Error handling is implemented and tested
- [ ] Performance requirements are met

**Quality Acceptance Criteria**:
- [ ] Code follows established patterns and standards
- [ ] Security considerations are addressed
- [ ] Accessibility requirements are met (frontend)
- [ ] Database migrations are properly handled
- [ ] Configuration changes are documented
- [ ] Breaking changes are documented and communicated

**Documentation Acceptance Criteria**:
- [ ] API documentation is updated
- [ ] Architecture decisions are documented
- [ ] Setup and deployment instructions are current
- [ ] Troubleshooting guides are updated
- [ ] Code comments explain complex logic

### Sprint Creation Guidelines

#### **Critical: Single Sprint Creation Rule**

**When creating a sprint from an analysis, ONLY create the first sprint initially.**

**Sprint Creation Process**:
1. **Create Only Sprint 1**: When asked to create a sprint from an analysis, create only `sprint-1.md`
2. **Stop After First Sprint**: Do not create additional sprints (sprint-2.md, sprint-3.md, etc.)
3. **Wait for Manual Review**: Allow time for manual review of the first sprint before proceeding
4. **Sequential Creation**: Additional sprints should only be created after explicit approval to proceed

**Rationale**:
- **Quality Control**: Ensures thorough review of sprint structure and approach
- **Risk Mitigation**: Prevents creating multiple sprints based on incorrect assumptions
- **Resource Management**: Allows assessment of actual effort before committing to multiple sprints
- **Feedback Integration**: Enables incorporation of feedback before creating subsequent sprints

**Exception**: This rule applies to sprint creation from analyses. If explicitly asked to create multiple sprints in a single request, follow that specific instruction.

### Sprint and Analysis Organization

#### Document Structure Requirements

**Sprint Documents** must follow this organized structure with date-based folders:
```
cursor-files/
├── sprints/
│   └── YYYY-MM-DD-[description]/
│       └── sprint-[nn].md
├── analysis/
│   └── YYYY-MM-DD-[description]/
│       └── [filename].md
└── templates/
    ├── SPRINT_STANDARDS.md
    └── SPRINT_TEMPLATE.md
```

**Date-Based Folder Structure**:
- **Format**: `YYYY-MM-DD-[description]`
- **YYYY-MM-DD**: Extract date portion from `date` command output and format as `YYYY-MM-DD` (e.g., "Sun Jan  4 20:11:19 PST 2026" → "2026-01-04")
- **Description**: Brief kebab-case description (e.g., `sprint-14-signal-improvement-integration`)

**Note**: The `**Date**:` field at the top of documents uses the full `date` command output (with time), but folder names use only the date portion in `YYYY-MM-DD` format.

**Examples**:
- `cursor-files/sprints/2025-12-30-signal-improvement-foundation/sprint-13-signal-improvement-foundation.md`
- `cursor-files/analysis/2026-01-04-sprint-14-signal-improvement-integration/sprint_14_analysis.md`

### File Numbering Rules

**Critical**: File numbering is **directory-scoped**, not date-scoped:

- **Each unique dated directory** starts with `sprint-1.md` (or descriptive name for analysis)
- **Numbering increments only within the same directory**
- **Different dated directories** can both have `sprint-1.md`

**Examples**:
- `2026-01-04/sprint-14-signal-improvement-integration/sprint-14-signal-improvement-integration.md` ✅
- `2025-12-30/signal-improvement-foundation/sprint-13-signal-improvement-foundation.md` ✅
- `2025-12-30/signal-improvement-foundation/sprint-14.md` ✅ (if sprint-13 exists in same directory)

**Important**: Sprint files are placed in `cursor-files/sprints/YYYY-MM-DD-[description]/` and analysis files are placed in `cursor-files/analysis/YYYY-MM-DD-[description]/`.

### Date Verification Requirements

**Critical**: Use the `date` command to verify today's date and time. Do NOT use filenames or modified dates on files to determine the current date, as these are not accurate indicators of the actual date.

**Required Date Verification Process**:
1. **Run Date Command**: Execute `date` command to get the current date and time
2. **Use Full Output for Date Field**: Use the exact `date` command output for the `**Date**:` field at the top of documents (includes time)
3. **Extract Date for Folder Names**: Extract the date portion and format as `YYYY-MM-DD` for directory names
4. **Verify Date**: Include the date command output as evidence in documentation

**Example Date Verification**:
```bash
# MANDATORY: Verify current date and time
date
# Output: Sun Jan  4 20:11:19 PST 2026
# Use for Date field: "Sun Jan  4 20:11:19 PST 2026"
# Use for folder name: "2026-01-04"
```

**Forbidden Date Sources**:
- File modification timestamps
- File creation dates
- Git commit dates
- Any other file system metadata
- Assumptions about current date

## 📊 Sprint Documentation Standards

### **Sprint Files (`sprint-{number}.md`)**

#### **Critical Structure**

```markdown
# [Sprint Name] - [Brief Description]

## Sprint Overview
**Sprint Goal**: [Clear, measurable, testable goal with specific success criteria]
**Sprint Duration**: [Exact time estimate in hours/days]
**Current Status**: [Specific technical state with file paths and configurations]
**Target Status**: [Exact desired end state with measurable outcomes]

## Sprint Phases

### Phase 1: [Phase Name] (Duration: X hours)
**Objective**: [Specific technical objective - what will be accomplished in this phase]
**Dependencies**: [List any external dependencies, tools, or setup required]
**Deliverables**: [Concrete, testable deliverables that can be verified]

### Phase 2: [Phase Name] (Duration: X hours)
**Objective**: [Specific technical objective building on Phase 1]
**Dependencies**: [Must complete Phase 1, plus any additional external dependencies]
**Deliverables**: [Concrete, testable deliverables that advance toward sprint goal]

### Phase 3: [Phase Name] (Duration: X hours)
**Objective**: [Specific technical objective completing main development work]
**Dependencies**: [Must complete Phase 2, plus any additional external dependencies]
**Deliverables**: [Concrete, testable deliverables that complete development work]

### Phase 4: Sprint Quality Assurance (Duration: 3-4 hours) [Critical]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic [Number]: [Epic Name]
**Priority**: [Critical/High/Medium/Low with business justification]
**Estimated Time**: [Exact hours with breakdown by story]
**Dependencies**: [Specific technical dependencies with file paths]
**Status**: [Not Started/In Progress/Completed]
**Phase Assignment**: [Which phase this epic belongs to]

#### Story [Number].[Number]: [Technically Specific Story Name]
- **ID**: [Unique identifier: SPRINT-EPIC-STORY format, e.g., S1-E1-S1]
- **Type**: [Feature/Bug Fix/Technical Debt/Research/Configuration/Refactor]
- **Priority**: [Critical/High/Medium/Low with technical justification]
- **Estimate**: [Exact hours with breakdown by task]
- **Phase**: [Which sprint phase this story belongs to (1, 2, 3, or 4)]
- **Prerequisites**: [Exact stories that must be completed first - use story IDs]
- **Files to Modify**: [Complete list of file paths that will be changed]
- **Files to Create**: [Complete list of new files with their purposes]
- **Dependencies**: [Exact technical dependencies: libraries, services, configurations]

- **Acceptance Criteria** (MUST be technically testable):
  - [ ] [Specific file exists at exact path with exact content or functionality]
  - [ ] [Specific function/method returns exact expected output for given input]
  - [ ] [Specific configuration produces exact expected behavior]
  - [ ] [Specific command executes without errors and produces exact output]
  - [ ] [Specific UI element exists with exact properties and behavior]

- **Technical Context**:
  - **Current State**: [Exact current implementation with code snippets]
  - **Required Changes**: [Precise changes needed with before/after examples]
  - **Integration Points**: [How this connects to existing system components]
  - **Data Structures**: [Exact data models, interfaces, or schemas involved]
  - **API Contracts**: [Exact endpoint signatures, request/response formats]

- **Implementation Steps** (MUST be executable without interpretation):
  1. **[Specific Action]**: [Exact command, file edit, or configuration change]
     - File: `[exact/file/path.ext]`
     - Action: [Create/Modify/Delete/Configure]
     - Content: [Exact code, configuration, or command]
  2. **[Specific Action]**: [Exact command, file edit, or configuration change]
     - File: `[exact/file/path.ext]`
     - Action: [Create/Modify/Delete/Configure]
     - Content: [Exact code, configuration, or command]
  3. **[Continue for all steps]**

- **Validation Steps** (MUST be executable commands):
  1. **[Test Command]**: `[exact command to run]`
     - Expected Output: [Exact expected result]
  2. **[Verification Step]**: [Exact check to perform]
     - Expected Result: [Exact expected outcome]

- **Definition of Done** (MUST be measurable):
  - [ ] All files in "Files to Modify" list have been updated
  - [ ] All files in "Files to Create" list exist with correct content
  - [ ] All validation steps pass with expected outputs
  - [ ] [Specific test suite] passes without errors
  - [ ] [Specific build command] completes successfully
  - [ ] [Specific functionality] works as demonstrated by [exact test]

- **Rollback Plan**: [Exact steps to undo changes if issues arise]
- **Risk Assessment**: [Specific technical risks with mitigation strategies]
- **Success Metrics**: [Quantifiable, measurable outcomes]

### Critical Final Stories (Every Sprint Must Include These)

#### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: [SPRINT-DOC-UPDATE]
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**:
  - [ ] **Frontend documentation** updated if frontend changes were made
  - [ ] **Backend documentation** updated if backend changes were made
  - [ ] **API documentation** updated if API changes were made
  - [ ] **Deployment documentation** updated if deployment/infrastructure changes were made
  - [ ] **Architecture documentation** updated if architectural changes were made
  - [ ] **User documentation** updated if user-facing features were changed
  - [ ] **Coding standards** updated if new patterns or practices were introduced
  - [ ] **Contribution guidelines** updated if development processes changed

#### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: [SPRINT-QG-VALIDATION]
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (MUST be 100% pass):
  - [ ] **Linting**: All linting checks pass with zero errors and zero warnings
  - [ ] **Type Checking**: All type checking passes with zero errors
  - [ ] **Unit Tests**: All unit tests pass (100% pass rate required)
  - [ ] **Integration Tests**: All integration tests pass (100% pass rate required)
  - [ ] **Build Process**: Build process completes without errors
  - [ ] **Code Formatting**: Code formatting is consistent
  - [ ] **Security**: No security vulnerabilities detected
  - [ ] **All acceptance criteria from previous stories verified as complete**

#### Story [FINAL]: Sprint Completion and Archive
- **ID**: [SPRINT-COMPLETION]
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**:
  - [ ] `completion-report.md` created with comprehensive sprint summary
  - [ ] All sprint files organized and complete in sprint directory
  - [ ] Sprint directory moved from `active/` to `completed/`
  - [ ] Any cross-references updated to point to completed location
  - [ ] Sprint marked as completed in any tracking systems
```

## 📐 Document Quality Standards

### **Emphasis Hierarchy System**

**Clear priority levels for requirements and guidelines:**

- **Critical**: Must be followed - failure results in invalid sprint
- **Important**: Should be followed - improves sprint quality significantly  
- **Recommended**: Best practice - enhances sprint completeness

### **Zero Ambiguity and Evidence-Based Analysis**

**Every section of every document MUST be extremely clear, specific, concise, explicit, and leave absolutely no room for confusion or interpretation.**

**Important**: For complete evidence-based analysis requirements, see `ANALYSIS_STANDARDS.md` lines 484-524.

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

#### **File Content Verification**
**Critical**: Before making ANY claim about code, configuration, or system state, you must:

1. **Read Actual File Contents**: Use `read_file` tool to examine exact file contents
2. **Run Verification Commands**: Execute specific commands to gather data
3. **Document Command Output**: Include exact command and verbatim response
4. **Verify Claims**: Cross-reference all statements with actual evidence

**IMPORTANT**: For complete evidence documentation format and forbidden practices, see `ANALYSIS_STANDARDS.md` lines 506-524.
- **NEVER** approximate measurements or counts
- **NEVER** report "mostly complete" - strive for 100% completion
- **NEVER** direct anyone to use git unless explicitly mentioned in the prompt by the prompter that git can be used

#### **DATE VERIFICATION REQUIREMENTS**
For `bball`, the most important time context is the **data snapshot** (raw files) and the **ingestion run identity** (DB).

- **MANDATORY**: Record UTC time and the exact artifacts being used.
- **MANDATORY**: Use `date -u` for timestamps included in docs.
- **FORBIDDEN**: Use file modification time as a proxy for the snapshot time.

```bash
date -u
source .env
echo "$DATABASE_URL"
```

#### **Database Access Setup**
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

#### **Database Verification Commands**

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

#### **Error Analysis Requirements**
- **Critical**: If analyzing errors, bugs, or failures, include complete root cause analysis
- **SECTION REQUIRED**: "Why This Error Occurred" section with:
  - **Primary Cause**: The fundamental reason why the error occurred
  - **Contributing Factors**: Secondary factors that enabled or worsened the error
  - **Timeline**: When the error was introduced and when it manifested
  - **Impact Analysis**: What systems/processes were affected
  - **Prevention Strategy**: How to prevent similar errors in the future

#### **Required Verification Steps**
1. **File Existence**: Verify files exist at claimed paths
2. **Content Accuracy**: Verify claimed content matches actual content
3. **Command Execution**: Verify commands work as documented
4. **Output Validation**: Verify expected outputs match actual outputs
5. **Cross-Reference**: Verify claims against multiple sources

### **Database Access and Verification (bball)**

Use `.env` with a single DSN variable:

```bash
cp env.example .env
source .env
echo "$DATABASE_URL"
```

#### **Database Evidence Documentation Format**

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

#### **Language Standards**
- **Specific Terms**: Use exact technical terms, not generic descriptions
- **Complete Sentences**: Every instruction must be a complete, actionable sentence
- **Active Voice**: Use active voice for all instructions and descriptions
- **Present Tense**: Use present tense for current states, future tense for planned changes
- **Precise Quantification**: Use exact numbers, not approximations
- **FORBIDDEN WORDS**: Never use "likely", "probably", "mostly", "generally", "typically", "usually", "about", "approximately", "seems", "appears", "might", "could", "should"
- **REQUIRED PRECISION**: Use definitive language: "is", "will", "does", "has", "contains", "requires", "implements"
- **CONCRETE STATEMENTS**: Every statement must be factual and verifiable, not speculative

#### **Technical Precision**
- **Exact Paths**: Always use complete file paths from project root
- **Complete Commands**: Include all flags, parameters, and options
- **Specific Versions**: Reference exact version numbers, not ranges
- **Full Configuration**: Show complete configuration blocks, not snippets
- **Concrete Examples**: Provide actual examples, not placeholders

### **Content Validation Checklist**

Before finalizing any document, verify it meets these requirements:

#### **Technical Accuracy**
- [ ] All file paths are correct and complete
- [ ] All commands are tested and work as documented
- [ ] All code examples are syntactically correct
- [ ] All configuration values are valid
- [ ] All dependencies are listed with correct versions

#### **Completeness**
- [ ] No steps are skipped or assumed
- [ ] All prerequisites are explicitly stated
- [ ] All expected outputs are defined
- [ ] All potential errors are addressed
- [ ] All file modifications are documented

#### **Clarity**
- [ ] Any developer can follow instructions without questions
- [ ] No ambiguous language or terms
- [ ] No assumptions about reader knowledge
- [ ] All technical terms are used consistently
- [ ] All examples are complete and realistic

#### **Validation Checklist**

**Before finalizing any sprint, verify**:
- [ ] **File Verification**: All file contents verified using `read_file` tool before making claims
- [ ] **Command Evidence**: All data gathering commands documented with exact commands and verbatim output
- [ ] **Date Verification**: Used `date` command to verify today's date (not file timestamps)
- [ ] **Database Verification**: Verified database access and contents before making database claims
- [ ] **No Assumptions**: No assumptions made about reader knowledge, system behavior, or implementation details
- [ ] **No Vague Language**: No use of "likely", "probably", "mostly", "generally", "typically", "usually", "about", "approximately", "seems", "appears", "might", "could", "should"
- [ ] **Definitive Language**: All statements use definitive language ("is", "will", "does", "has", "contains", "requires", "implements")
- [ ] **Concrete Evidence**: Every claim backed by specific, verifiable evidence
- [ ] **Perfect Completeness**: Sprint is 100% complete, not "mostly complete"
- [ ] **Honest Assessment**: Actual findings reported, not assumptions or expectations
- [ ] **Technical Specificity**: Every story is technically explicit and developer-ready
- [ ] **Acceptance Criteria**: All acceptance criteria are technically testable
- [ ] **Implementation Steps**: All steps are executable without interpretation
- [ ] **Validation Steps**: All validation steps are executable commands
- [ ] **Definition of Done**: All definitions of done are measurable
- [ ] **Risk Assessment**: All risks have specific mitigation strategies
- [ ] **Success Metrics**: All success metrics are quantifiable

## 📋 File Organization Rules & Naming Standards

### **File Organization Principles**

#### **Hierarchical Organization**
- **Primary**: By document type (analyses, sprints, standards)
- **Secondary**: By date (chronological ordering)
- **Tertiary**: By functional area (modules, features, components)

#### **Temporal Organization**
- **Active Work**: Current analyses and sprints in progress
- **Completed Work**: Archived analyses and completed sprints
- **Reference Materials**: Standards, templates, and guidelines

#### **Functional Organization**
- **Module-Specific**: Documentation grouped by system modules
- **Cross-Cutting**: Documentation that spans multiple modules
- **Infrastructure**: Deployment, configuration, and operational documentation

### **File Naming Standards**

#### **Sprint Documents**
- **Format**: `sprint-{number}.md` where number starts at 1 and increments if file already exists
- **Examples**:
  - `sprint-1.md` (first sprint in the directory)
  - `sprint-2.md` (second sprint if sprint-1.md already exists)
  - `sprint-3.md` (third sprint if sprint-1.md and sprint-2.md already exist)


#### **Directory Naming**
Sprint documents live under `cursor-files/sprints/YYYY-MM-DD-[description]/` in this repo.

**Date-Based Folder Structure**:
- **Format**: `YYYY-MM-DD-[description]`
- **YYYY-MM-DD**: Extract date portion from `date` command output and format as `YYYY-MM-DD` (e.g., "Sun Jan  4 20:11:19 PST 2026" → "2026-01-04")
- **Description**: Brief kebab-case description (e.g., `sprint-14-signal-improvement-integration`)

**Note**: The `**Date**:` field at the top of documents uses the full `date` command output (with time), but folder names use only the date portion in `YYYY-MM-DD` format.

**Examples**:
- `cursor-files/sprints/2025-12-30-signal-improvement-foundation/sprint-13-signal-improvement-foundation.md`
- `cursor-files/analysis/2026-01-04-sprint-14-signal-improvement-integration/sprint_14_analysis.md`

#### **File Numbering Rules**
- **Check Existing Files**: Before creating a new file, check if numbered files already exist in the same directory
- **Increment Number**: If `sprint-13.md` exists, create `sprint-14.md`
- **Continue Incrementing**: Keep incrementing until you find a number that doesn't exist
- **No Gaps**: Do not skip numbers (e.g., don't create sprint-15.md if sprint-14.md doesn't exist)
- **Directory-Scoped**: Numbering is scoped to the directory (different dated directories can both have sprint-1.md)

#### **Standards Documents**
- **Format**: `descriptive_name_standards.md`
- **Examples**:
  - `coding_standards.md`
  - `api_design_standards.md`

### **Directory Structure Standards**

#### **Sprint Directory Structure**
```
cursor-files/
├── sprints/
│   └── YYYY-MM-DD-[description]/
│       └── sprint-[nn].md
├── analysis/
│   └── YYYY-MM-DD-[description]/
│       └── [filename].md
```

#### **Document Placement Rule (bball)**

- Put sprint plans in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`.
- Put analysis docs in `cursor-files/analysis/YYYY-MM-DD-[description]/[filename].md`.
- **Date Verification**: Always use `date` command to get current date and time. Use full output for `**Date**:` field at top of documents, extract `YYYY-MM-DD` for folder names.

## 📖 Quick Navigation

### **Sprint Documentation**
- **Sprint Standards**: `cursor-files/templates/SPRINT_STANDARDS.md` (this document)
- **Sprint Template**: `cursor-files/templates/SPRINT_TEMPLATE.md` (sprint document template)

### **File Organization Help**
- **Sprint Standards**: `cursor-files/templates/SPRINT_STANDARDS.md` (this document)
- **Sprint Template**: `cursor-files/templates/SPRINT_TEMPLATE.md` (sprint document template)
- **File Placement Rules**: See "File Organization Rules" section above
- **Naming Standards**: See "File Naming Standards" section above
- **Run Context**: See "DATE VERIFICATION REQUIREMENTS" section above
