package devops.identity

test_session_owner_allowed if {
	result := decision with input as {"subject": {"id": "user-1", "role": "developer"}, "action": "identity.sessions.read", "resource": {"kind": "session", "owner_id": "user-1"}}
	result.allow
}

test_other_user_denied if {
	result := decision with input as {"subject": {"id": "user-1", "role": "developer"}, "action": "identity.sessions.read", "resource": {"kind": "session", "owner_id": "user-2"}}
	result.allow == false
}

test_project_admin_allowed if {
	result := decision with input as {"subject": {"id": "user-1", "role": "admin", "project_id": "project-1"}, "action": "identity.members.write", "resource": {"kind": "project_membership", "project_id": "project-1"}}
	result.allow
}

test_unknown_action_denied if {
	result := decision with input as {"subject": {"id": "user-1", "role": "admin", "project_id": "project-1"}, "action": "identity.users.delete", "resource": {"kind": "user"}}
	result.allow == false
}

test_other_project_denied if {
	result := decision with input as {"subject": {"id": "user-1", "role": "admin", "project_id": "project-2"}, "action": "identity.members.write", "resource": {"kind": "project_membership", "project_id": "project-1"}}
	result.allow == false
}

test_developer_cannot_manage_members if {
	result := decision with input as {"subject": {"id": "user-1", "role": "developer", "project_id": "project-1"}, "action": "identity.members.write", "resource": {"kind": "project_membership", "project_id": "project-1"}}
	result.allow == false
}

test_missing_input_denied if {
	result := decision with input as {}
	result.allow == false
}

test_select_member_project_allowed if {
	result := decision with input as {"subject": {"id": "user-1", "role": "developer", "project_id": "project-1"}, "action": "identity.project.select", "resource": {"kind": "session", "owner_id": "user-1", "project_id": "project-1"}}
	result.allow
}

test_select_other_project_denied if {
	result := decision with input as {"subject": {"id": "user-1", "role": "developer", "project_id": "project-1"}, "action": "identity.project.select", "resource": {"kind": "session", "owner_id": "user-1", "project_id": "project-2"}}
	result.allow == false
}

test_null_subject_denied if {
	result := decision with input as {"subject": {"id": null}, "action": "identity.sessions.read", "resource": {"kind": "session", "owner_id": null}}
	result.allow == false
}
