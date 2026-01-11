# Sprint Template: [Sprint Name] - [Brief Description]

**Date**: [Use `date` command output, e.g., "Sun Jan  4 20:11:19 PST 2026"]  
**Sprint Duration**: [X] days ([Y] hours total)  
**Sprint Goal**: [Clear, measurable, testable goal with specific success criteria]  
**Current Status**: [Specific technical state with file paths and configurations]  
**Target Status**: [Exact desired end state with measurable outcomes]  
**Team Size**: [Number of developers]  
**Sprint Lead**: [Lead developer name]  

## Sprint Standards Reference

**Important**: This sprint must follow the comprehensive standards defined in `SPRINT_STANDARDS.md`. 

**Key Requirements**:
- **Evidence-Based**: Every claim must be backed by concrete evidence (commands + verbatim output, code refs, DB queries).
- **Run Context**: Record UTC time, `.env`/`DATABASE_URL`, and the exact raw artifacts / ingestion identifiers involved.
- **File Verification**: Verify file contents directly before making claims.
- **Database Verification**: PostgreSQL via `DATABASE_URL` (see `env.example`, `docker-compose.yml`, `scripts/migrate.py`, `scripts/psql.sh`).
- **Document Placement**: Sprint plans live in `cursor-files/sprints/YYYY-MM-DD-[description]/sprint-[nn].md`. Always use `date` command to verify current date and format as `YYYY-MM-DD`.

**See `SPRINT_STANDARDS.md` for complete requirements and validation checklist.**

## Pre-Sprint Code Quality Baseline
- **Test Results**: [Pass rate and failed tests]
- **QC Results**: [Pass/fail and key check counts]
- **Code Coverage**: [Coverage percentage and missing lines]
- **Build Status**: [Build success and issues]

**Purpose**: This baseline ensures we maintain or improve code quality throughout the sprint and provides historical reference for quality metrics.

## Database Evidence Template
**Note**: This repo uses PostgreSQL via `DATABASE_URL` (see `env.example`). Setup instructions are in `cursor-files/templates/SPRINT_STANDARDS.md`.
- **DO NOT modify database** - no INSERT, UPDATE, ALTER, TRUNCATE, DELETE unless part of sprint plan
- **DO NOT modify database users** - no user management or system changes

## Git Usage Restrictions

**CRITICAL RESTRICTION**: Sprint participants must NOT use git at all unless explicitly directed to by the analysis and sprint plan.

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

## Sprint Overview

### Business Context
- **Business Driver**: [Why this sprint is needed - business problem or opportunity]
- **Success Criteria**: [Measurable business outcomes]
- **Stakeholders**: [Who is affected by this sprint]
- **Timeline Constraints**: [Any hard deadlines or dependencies]

### Technical Context
- **Current System State**: [Detailed technical state with specific file references]
- **Target System State**: [Exact desired technical state]
- **Architecture Impact**: [How this sprint affects system architecture]
- **Integration Points**: [External systems or services affected]

### Sprint Scope
- **In Scope**: [Specific features, fixes, or improvements included]
- **Out of Scope**: [Explicitly excluded items]
- **Assumptions**: [Key assumptions made for this sprint]
- **Constraints**: [Technical, business, or resource constraints]

## Sprint Phases

### Phase 1: [Phase Name] (Duration: [X] hours)
**Objective**: [Specific technical objective]
**Dependencies**: [External dependencies, tools, or setup required]
**Deliverables**: [Concrete, testable deliverables]

### Tasks
- **[Task 1.1]**: [Specific task description]
  - **Files**: [Files to modify/create]
  - **Effort**: [Hours]
  - **Prerequisites**: [Dependencies]
  - **Validation**: [How to verify completion]

### Phase 2: [Phase Name] (Duration: [X] hours)
**Objective**: [Specific technical objective]
**Dependencies**: [Must complete Phase 1, plus additional dependencies]
**Deliverables**: [Concrete, testable deliverables]

### Tasks
- **[Task 2.1]**: [Specific task description]
  - **Files**: [Files to modify/create]
  - **Effort**: [Hours]
  - **Prerequisites**: [Dependencies]
  - **Validation**: [How to verify completion]

### Phase 3: [Phase Name] (Duration: [X] hours)
**Objective**: [Specific technical objective]
**Dependencies**: [Must complete Phase 2, plus additional dependencies]
**Deliverables**: [Concrete, testable deliverables]

### Tasks
- **[Task 3.1]**: [Specific task description]
  - **Files**: [Files to modify/create]
  - **Effort**: [Hours]
  - **Prerequisites**: [Dependencies]
  - **Validation**: [How to verify completion]

### Phase 4: Sprint Quality Assurance (Duration: 3-4 hours) [MANDATORY]
**Objective**: Update documentation, validate all sprint work meets quality standards, and complete sprint
**Dependencies**: Must complete Phase 3 successfully
**Deliverables**: Updated documentation, 100% passing quality gates, and sprint archive

## Sprint Backlog

### Epic 1: [Epic Name]
**Priority**: [Critical/High/Medium/Low with business justification]
**Estimated Time**: [X] hours ([Y] hours per story breakdown)
**Dependencies**: [Specific technical dependencies with file paths]
**Status**: [Not Started/In Progress/Completed]
**Phase Assignment**: [Which phase this epic belongs to]

### Story 1.1: [Technically Specific Story Name]
- **ID**: [S1-E1-S1] (Sprint-Epic-Story format)
- **Type**: [Feature/Bug Fix/Technical Debt/Research/Configuration/Refactor]
- **Priority**: [Critical/High/Medium/Low with technical justification]
- **Estimate**: [X] hours ([Y] hours breakdown by task)
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
  - [ ] [Specific test suite] passes without errors
  - [ ] [Specific build command] completes successfully

- **Technical Context**:
  - **Current State**: [Exact current implementation with code snippets]
    ```[language]
    # Example current code
    def current_function():
        return "current implementation"
    ```
  - **Required Changes**: [Precise changes needed with before/after examples]
    ```[language]
    # After implementation
    def new_function():
        return "new implementation"
    ```
  - **Integration Points**: [How this connects to existing system components]
  - **Data Structures**: [Exact data models, interfaces, or schemas involved]
  - **API Contracts**: [Exact endpoint signatures, request/response formats]

- **Implementation Steps**: [Exact commands, file edits, or configuration changes]
- **Validation Steps**: [Executable commands with expected outputs]

- **Definition of Done**: [Measurable completion criteria]
- **Rollback Plan**: [Steps to undo changes if issues arise]
- **Risk Assessment**: [Technical risks with mitigation strategies]

- **Success Metrics**: [Quantifiable, measurable outcomes]
  - **Performance**: [Specific performance metrics]
  - **Quality**: [Specific quality metrics]
  - **Functionality**: [Specific functionality metrics]

### Epic 2: [Epic Name]
**Priority**: [Critical/High/Medium/Low with business justification]
**Estimated Time**: [X] hours ([Y] hours per story breakdown)
**Dependencies**: [Specific technical dependencies with file paths]
**Status**: [Not Started/In Progress/Completed]
**Phase Assignment**: [Which phase this epic belongs to]

### Story 2.1: [Story Name]
- **ID**: [S1-E2-S1]
- **Type**: [Feature/Bug Fix/Technical Debt/Research/Configuration/Refactor]
- **Priority**: [Critical/High/Medium/Low]
- **Estimate**: [X] hours
- **Phase**: [Which sprint phase this story belongs to]
- **Prerequisites**: [Stories that must be completed first]
- **Files**: [Files to modify/create]
- **Dependencies**: [Technical dependencies]

- **Acceptance Criteria**: [Technically testable criteria]
- **Technical Context**: [Current state and required changes]
- **Implementation Steps**: [Executable commands and file changes]
- **Validation Steps**: [Executable commands with expected outputs]
- **Definition of Done**: [Measurable completion criteria]
- **Rollback Plan**: [Steps to undo changes if needed]
- **Risk Assessment**: [Technical risks with mitigation strategies]
- **Success Metrics**: [Quantifiable outcomes]

## MANDATORY FINAL STORIES (Every Sprint Must Include These)

### Story [THIRD-TO-LAST]: Documentation Update
- **ID**: [SPRINT-DOC-UPDATE]
- **Type**: Documentation Maintenance
- **Priority**: High
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL development stories completed

- **Acceptance Criteria**: [All relevant documentation updated]
- **Technical Context**: [Current state and required changes]
- **Implementation Steps**: [Update documentation as needed]
- **Validation Steps**: [Verify documentation is complete]

### Story [SECOND-TO-LAST]: Quality Gate Validation
- **ID**: [SPRINT-QG-VALIDATION]
- **Type**: Quality Assurance
- **Priority**: Critical
- **Estimate**: 1-2 hours
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: ALL other sprint stories completed

- **Acceptance Criteria** (100% pass required):
  - [ ] All linting checks pass with zero errors and warnings
  - [ ] All tests pass (100% pass rate required)
  - [ ] Build process completes without errors
  - [ ] Code quality maintained or improved
  - [ ] All previous story acceptance criteria verified

- **Technical Context**:
  - **Current State**: [Current state of codebase]
  - **Required Changes**: [Any fixes needed to pass quality gates]
  - **Quality Gates**: [Specific quality checks to run]

- **Implementation Steps**: [Run quality checks and fix any issues]
- **Validation Steps**: [Verify all quality gates pass]

### Story [FINAL]: Sprint Completion and Archive
- **ID**: [SPRINT-COMPLETION]
- **Type**: Sprint Management
- **Priority**: Critical
- **Estimate**: 1 hour
- **Phase**: Phase 4 (Sprint Quality Assurance)
- **Prerequisites**: Quality Gate Validation story completed successfully

- **Acceptance Criteria**: [Sprint completion report created and sprint archived]
- **Technical Context**: [Current sprint state and archive tasks]
- **Implementation Steps**: [Create report, organize files, archive sprint]
- **Validation Steps**: [Verify archive and report completion]

## Technical Decisions

### Design Pattern Analysis

### Design Pattern: [Pattern Name]
- **Category**: [Architectural/Creational/Structural/Behavioral]
- **Intent**: [Why this pattern was chosen]
- **Implementation**: [Implementation details with code references]
- **Benefits**: [Specific advantages gained]
- **Trade-offs**: [Disadvantages or limitations]
- **Rationale**: [Why this pattern was chosen]

### Algorithm Analysis

### Algorithm: [Algorithm Name]
- **Type**: [Search/Sort/Graph/Dynamic Programming/etc.]
- **Complexity**: Time O(?), Space O(?)
- **Description**: [How the algorithm works]
- **Use Case**: [Why this algorithm was chosen]
- **Performance**: [Performance characteristics and benefits]

### Design Decision Analysis

### Design Decision: [Decision Title]
- **Problem**: [Clear description of the problem being solved]
- **Context**: [Constraints and success criteria]
- **Project Scope**: [Project size, team size, expected growth, timeline constraints]
- **Options**: [Multiple solution alternatives considered]
- **Selected**: [Chosen solution with rationale]

**Option 3: [Chosen Alternative] (CHOSEN)**
- **Design Pattern**: [Exact pattern name]
- **Algorithm**: [Big O notation if applicable]
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

**Risk Assessment**: [Technical risks with mitigation strategies]
**Trade-off Analysis**: [What was sacrificed vs. what was gained, net benefit assessment]

## Testing Strategy

### Testing Approach
- **Unit Tests**: [Coverage target and execution]
- **Integration Tests**: [Integration points and environment]
- **E2E Tests**: [Key user journeys and environment]
- **Performance Tests**: [Performance targets and monitoring]

## Deployment Plan
- **Pre-Deployment**: [Checklist of prerequisites]
- **Deployment Steps**: [Specific deployment actions]
- **Post-Deployment**: [Validation and monitoring steps]
- **Rollback Plan**: [Steps to undo changes if needed]

## Risk Assessment
- **Technical Risks**: [Technical risks with mitigation strategies]
- **Business Risks**: [Business risks with mitigation strategies]
- **Resource Risks**: [Resource risks with mitigation strategies]

## Success Metrics
- **Technical**: [Code quality, performance, test coverage, bug rate]
- **Business**: [User satisfaction, feature adoption, system reliability]
- **Sprint**: [Velocity, burndown, quality gates]

## Sprint Completion Checklist
- [ ] All stories completed according to acceptance criteria
- [ ] All code reviewed and approved
- [ ] All tests written and passing
- [ ] All documentation updated
- [ ] All quality gates pass (linting, type checking, tests, build, security)

### Post-Sprint Quality Comparison
- **Test Results**: [Pass rate and quality change]
- **Linting Results**: [Error/warning counts and quality change]
- **Code Coverage**: [Coverage percentage and quality change]
- **Build Status**: [Build success and quality change]
- **Overall Assessment**: [Overall quality impact of sprint]

### Documentation and Closure
- [ ] All relevant documentation updated
- [ ] Sprint completion report created
- [ ] Sprint files organized and archived
- [ ] Sprint marked as completed

---

## Document Validation
**Important**: Use the comprehensive validation checklist in `SPRINT_STANDARDS.md` to ensure this sprint meets all quality standards.
