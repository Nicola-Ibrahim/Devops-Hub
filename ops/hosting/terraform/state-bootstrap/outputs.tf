output "state_bucket_name" {
  value       = aws_s3_bucket.terraform_state.bucket
  description = "Bucket name to provide with the AWS platform backend configuration."
}
