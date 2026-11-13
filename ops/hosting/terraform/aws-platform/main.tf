data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_caller_identity" "current" {}

locals {
  common_tags = {
    Project     = "DevOpsHub"
    ManagedBy   = "Terraform"
    Environment = "platform-host"
  }
  account_id         = data.aws_caller_identity.current.account_id
  ecr_repository     = "${var.name_prefix}/platform"
  ecr_repository_arn = "arn:aws:ecr:${var.aws_region}:${local.account_id}:repository/${local.ecr_repository}"
  backup_bucket_name = "${var.name_prefix}-${local.account_id}-${var.aws_region}-backup"
  ec2_instance_arn   = "arn:aws:ec2:${var.aws_region}:${local.account_id}:instance/${aws_instance.platform.id}"
  oidc_subject_main  = "repo:${var.github_repository}:ref:refs/heads/main"
  oidc_subject_prod  = "repo:${var.github_repository}:environment:production"
}

resource "aws_vpc" "platform" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.common_tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "platform" {
  vpc_id = aws_vpc.platform.id
  tags   = merge(local.common_tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_subnet" "platform" {
  vpc_id                  = aws_vpc.platform.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = merge(local.common_tags, { Name = "${var.name_prefix}-public" })
}

resource "aws_route_table" "platform" {
  vpc_id = aws_vpc.platform.id
  tags   = merge(local.common_tags, { Name = "${var.name_prefix}-public" })
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.platform.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.platform.id
}

resource "aws_route_table_association" "platform" {
  subnet_id      = aws_subnet.platform.id
  route_table_id = aws_route_table.platform.id
}

resource "aws_security_group" "platform" {
  name        = "${var.name_prefix}-host"
  description = "HTTPS/HTTP ingress; optional restricted SSH. No database ingress."
  vpc_id      = aws_vpc.platform.id
  tags        = local.common_tags

  ingress {
    description = "HTTPS through Nginx"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP ACME challenge and redirect only"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  dynamic "ingress" {
    for_each = var.ssh_ingress_cidrs
    content {
      description = "SSH only from operator-approved network"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    description = "Outbound package, image, SSM and certificate connections"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecr_repository" "platform" {
  name                 = local.ecr_repository
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  tags                 = local.common_tags

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_iam_role" "host" {
  name               = "${var.name_prefix}-host"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ssm_host" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "ecr_pull" {
  name = "ecr-pull-platform-images"
  role = aws_iam_role.host.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = local.ecr_repository_arn
      }
    ]
  })
}

resource "aws_s3_bucket" "platform_backups" {
  bucket        = local.backup_bucket_name
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }

  tags           = merge(local.common_tags, { Purpose = "encrypted-platform-control-plane-backups" })
}

resource "aws_s3_bucket_public_access_block" "platform_backups" {
  bucket                  = aws_s3_bucket.platform_backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "platform_backups" {
  bucket = aws_s3_bucket.platform_backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "platform_backups" {
  bucket = aws_s3_bucket.platform_backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "platform_backups" {
  bucket = aws_s3_bucket.platform_backups.id
  rule {
    id     = "retain-encrypted-control-plane-backups"
    status = "Enabled"
    filter {
      prefix = "control-plane/"
    }
    expiration {
      days = 90
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_policy" "platform_backups_tls" {
  bucket = aws_s3_bucket.platform_backups.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.platform_backups.arn,
        "${aws_s3_bucket.platform_backups.arn}/*"
      ]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.platform_backups]
}

resource "aws_iam_role_policy" "backup_upload" {
  name = "write-encrypted-control-plane-backups"
  role = aws_iam_role.host.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:AbortMultipartUpload"]
      Resource = "${aws_s3_bucket.platform_backups.arn}/control-plane/*"
    }]
  })
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.name_prefix}-host"
  role = aws_iam_role.host.name
}

resource "aws_instance" "platform" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.platform.id
  vpc_security_group_ids      = [aws_security_group.platform.id]
  iam_instance_profile        = aws_iam_instance_profile.host.name
  key_name                    = var.ssh_key_name
  associate_public_ip_address = true
  user_data                   = templatefile("${path.module}/user_data.sh.tftpl", {
    aws_region               = var.aws_region
    volume_id                = aws_ebs_volume.platform_data.id
    storage_helper_base64    = base64encode(file("${path.module}/../../scripts/helpers/configure_docker_storage.py"))
    data_volume_script_base64 = base64encode(file("${path.module}/../../scripts/initialize-data-volume.sh"))
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = var.host_disk_gib
  }

  tags = merge(local.common_tags, { Name = "${var.name_prefix}-host" })
}

resource "aws_ebs_volume" "platform_data" {
  availability_zone = aws_subnet.platform.availability_zone
  size              = var.docker_data_disk_gib
  type              = "gp3"
  encrypted         = true
  final_snapshot    = true
  tags              = merge(local.common_tags, {
    Name    = "${var.name_prefix}-docker-data"
    Purpose = "devops-hub-docker-data"
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_volume_attachment" "platform_data" {
  device_name = "/dev/sdf"
    volume_id                = aws_ebs_volume.platform_data.id
  instance_id = aws_instance.platform.id
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [var.github_oidc_thumbprint]
  tags            = local.common_tags
}

resource "aws_iam_role" "github_image_publisher" {
  name               = "${var.name_prefix}-github-publish"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = local.oidc_subject_main
        }
      }
    }]
  })
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "github_publish" {
  name = "publish-platform-images"
  role = aws_iam_role.github_image_publisher.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeImages",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart"
        ]
        Resource = local.ecr_repository_arn
      }
    ]
  })
}

resource "aws_iam_role" "github_deployer" {
  name               = "${var.name_prefix}-github-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = local.oidc_subject_prod
        }
      }
    }]
  })
  tags               = local.common_tags
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "deploy-platform-through-ssm"
  role = aws_iam_role.github_deployer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:SendCommand"]
        Resource = [
          "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
          local.ec2_instance_arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetCommandInvocation"]
        Resource = "*"
      }
    ]
  })
}
