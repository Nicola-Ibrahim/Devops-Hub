output "aws_region" {
  description = "Region used by the release workflows."
  value       = var.aws_region
}

output "aws_account_id" {
  description = "Account component for the image workflow configuration."
  value       = data.aws_caller_identity.current.account_id
}

output "instance_id" {
  description = "SSM target ID for the deploy workflow."
  value       = aws_instance.platform.id
}

output "docker_data_volume_id" {
  description = "Encrypted EBS volume storing Docker's persistent data root."
  value       = aws_ebs_volume.platform_data.id
}

output "public_ip" {
  description = "Host public IP; only ports 80/443 and configured SSH CIDRs are admitted."
  value       = aws_instance.platform.public_ip
}

output "ecr_repository_url" {
  description = "Immutable-tag ECR repository used by image release workflow."
  value       = aws_ecr_repository.platform.repository_url
}

output "backup_bucket_name" {
  description = "Private bucket for age-encrypted control-plane backup artifacts."
  value       = aws_s3_bucket.platform_backups.bucket
}

output "github_publish_role_arn" {
  description = "GitHub OIDC role for pushes from main."
  value       = aws_iam_role.github_image_publisher.arn
}

output "github_deploy_role_arn" {
  description = "GitHub OIDC role available only to the production environment."
  value       = aws_iam_role.github_deployer.arn
}

