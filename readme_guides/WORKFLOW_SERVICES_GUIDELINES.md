### Workflow Service Usage Guidelines

**Critical Workflow for Tasks Pertaining to Workflow Objects - Always Follow This Order:**

For glossary objects like data classes and business terms:
1. Use **list_data_classes_by_search_term** or **list_business_terms_by_search_term** first to find the artifact_id
2. Then call **list_user_tasks_approval_data_for_artifact** with the artifact_id to get approval data
3. NEVER use **get_asset_details** for data classes and business terms

For task inbox management:
1. Use **get_workflow_tasks_from_my_inbox** to see tasks assigned to you
2. Use task_title field (e.g., "Review Business term Ager") for display, not task_name
3. NEVER show user ID numbers - always display user's first and last name

For workflow monitoring:
1. Use **get_my_workflows** to see workflows you've initiated
1. Use **get_my_workflows** to see workflows you've initiated
2. Use **get_my_workflows** with deep_dive=True for detailed analysis with stalled detection and assignee information
**Important Display Requirements:**
- Show task_title instead of task_name when available
- Display workflow status instead of state
- Format user information as "FirstName LastName" instead of user IDs
- Show claimed status for tasks (Yes/No)
- Display due dates with status indicators (⚠ for at risk, ❌ for overdue)

