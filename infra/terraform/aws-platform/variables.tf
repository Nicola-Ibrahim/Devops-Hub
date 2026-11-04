variable "aws_region" {
  description = "AWS region for the single Docker-host target."
  type        = string
  default     = "eu-central-1"
}

variable "name_prefix" {
  description = "Short prefix for resources created by this configuration."
  type        = string
  default     = "devops-hub"

  validation {
    condition     = length(var.name_prefix) >= 3 && length(var.name_prefix) <= 25 && can(regex("^[a-z][a-z0-9-]+$", var.name_prefix))
    error_message = "name_prefix must be 3-25 lowercase letters, digits or hyphens and start with a letter."
  }
}

variable "github_repository" {
  description = "GitHub owner/repository allowed to publish and deploy images."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Set github_repository to the exact owner/repository name."
  }
}

variable "github_oidc_thumbprint" {
  description = "Validated SHA-1 TLS certificate thumbprint for token.actions.githubusercontent.com."
  type        = string

  validation {
    condition     = can(regex("^[0-9A-Fa-f]{40}$", var.github_oidc_thumbprint))
    error_message = "Supply the current 40-character GitHub OIDC TLS thumbprint from AWS/GitHub guidance."
  }
}

variable "ssh_ingress_cidrs" {
  description = "Optional operator VPN /32 or approved CIDRs for SSH. Empty disables SSH ingress."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([
      for cidr in var.ssh_ingress_cidrs : can(cidrhost(cidr, 0)) &&
      !contains(["0.0.0.0/0", "::/0"], cidr) && !strcontains(cidr, ":")
    ])
    error_message = "Each SSH ingress range must be a valid CIDR. Do not use 0.0.0.0/0."
  }
}

variable "ssh_key_name" {
  description = "Existing AWS EC2 key pair name used only for restricted Ansible SSH access."
  type        = string
  default     = null

  validation {
    condition     = length(var.ssh_ingress_cidrs) == 0 || (var.ssh_key_name != null && length(var.ssh_key_name) > 0)
    error_message = "If SSH ingress CIDRs are configured, ssh_key_name must name an existing EC2 key pair."
  }
}

variable "instance_type" {
  description = "EC2 instance class for the Docker target. Review cost and capacity before apply."
  type        = string
  default     = "t3.large"
}

variable "host_disk_gib" {
  description = "Encrypted gp3 root disk size."
  type        = number
  default     = 100

  validation {
    condition     = var.host_disk_gib >= 40 && var.host_disk_gib <= 500
    error_message = "host_disk_gib must be between 40 and 500 GiB."
  }
}

variable "docker_data_disk_gib" {
  description = "Encrypted persistent EBS capacity for Docker data, including the control-plane volume."
  type        = number
  default     = 200

  validation {
    condition     = var.docker_data_disk_gib >= 40 && var.docker_data_disk_gib <= 2000
    error_message = "docker_data_disk_gib must be between 40 and 2000 GiB."
  }
}
