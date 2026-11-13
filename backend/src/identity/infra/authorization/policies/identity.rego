package devops.identity

default decision := {"allow": false, "policy_revision": "identity-v1"}

decision := {"allow": true, "policy_revision": "identity-v1"} if {
	is_string(input.subject.id)
	input.subject.id != ""
	input.action in {"identity.sessions.read", "identity.sessions.revoke", "identity.logout", "identity.logout_all", "identity.password.change"}
	input.resource.kind == "session"
	input.subject.id == input.resource.owner_id
}

decision := {"allow": true, "policy_revision": "identity-v1"} if {
	is_string(input.subject.id)
	input.subject.id != ""
	input.action == "identity.project.select"
	input.resource.kind == "session"
	input.subject.id == input.resource.owner_id
	input.subject.role in {"developer", "admin"}
	input.subject.project_id == input.resource.project_id
	is_string(input.resource.project_id)
	input.resource.project_id != ""
}

decision := {"allow": true, "policy_revision": "identity-v1"} if {
	is_string(input.subject.id)
	input.subject.id != ""
	input.action in {"identity.members.read", "identity.members.write"}
	input.resource.kind == "project_membership"
	input.subject.role == "admin"
	input.subject.project_id == input.resource.project_id
	input.resource.project_id != null
	is_string(input.resource.project_id)
	input.resource.project_id != ""
}
