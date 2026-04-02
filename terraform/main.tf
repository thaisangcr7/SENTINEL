# main.tf — The core Terraform file that provisions our AWS infrastructure
#
# ┌──────────────────────────────────────────────────────────────────────────┐
# │ WHAT WE DID BEFORE THIS FILE (prerequisites):                          │
# │                                                                         │
# │ 1. Created an AWS account at https://aws.amazon.com                    │
# │ 2. In the AWS console, went to IAM → Users → Create user              │
# │    - Named it "terraform"                                              │
# │    - Attached the "AdministratorAccess" policy                         │
# │    - Created an access key (Security credentials → CLI)                │
# │ 3. Installed AWS CLI:  brew install awscli                             │
# │ 4. Ran:  aws configure                                                │
# │    - Pasted the Access Key ID and Secret Access Key                    │
# │    - Region: us-east-1                                                 │
# │    - Output format: json                                               │
# │ 5. Installed Terraform:  brew install hashicorp/tap/terraform          │
# │ 6. Verified both with:                                                 │
# │    - terraform --version  → v1.14.8                                    │
# │    - aws sts get-caller-identity  → showed our terraform user          │
# └──────────────────────────────────────────────────────────────────────────┘
#
# WHAT THIS FILE DOES:
# Creates a single EC2 instance (a virtual server on AWS) that will run SENTINEL.
# It also creates a security group (a firewall) that controls who can connect.
#
# How the pieces connect:
#   main.tf      → defines WHAT to build (EC2, security group, key pair)
#   variables.tf → defines configurable values (region, instance type)
#   outputs.tf   → defines what Terraform prints after it finishes (the server IP)

# Pattern: Terraform Provider
# Tells Terraform which cloud platform to use and which region to deploy in.
# "hashicorp/aws" is the official AWS plugin that Terraform downloads automatically.
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}


# Pattern: Data Source (lookup existing information)
# We need the AMI ID (Amazon Machine Image = the operating system template).
# Instead of hardcoding it, we ask AWS: "give me the latest Ubuntu 22.04 image."
# This way it stays up to date automatically.
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical (the company that makes Ubuntu)

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}


# Pattern: Key Pair
# To SSH into the EC2 instance, AWS needs your public SSH key.
# This uploads your existing key (~/.ssh/id_ed25519.pub) to AWS
# so the instance trusts your laptop when you connect.
resource "aws_key_pair" "sentinel" {
  key_name   = "sentinel-key"
  public_key = file(var.ssh_public_key_path)
}


# Pattern: Security Group (Firewall Rules)
# By default, AWS blocks ALL traffic to a new instance.
# We need to open specific ports so we can connect:
#   - Port 22  → SSH (so we can log in and manage the server)
#   - Port 8000 → Our FastAPI app (so clients can hit the API)
#   - Outbound  → Allow all (so the server can download packages, call FRED API, etc.)
resource "aws_security_group" "sentinel" {
  name        = "sentinel-sg"
  description = "Allow SSH and app traffic for SENTINEL"

  # Inbound: allow SSH from anywhere (port 22)
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Inbound: allow our FastAPI app (port 8000)
  ingress {
    description = "FastAPI app"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound: allow everything (server needs to reach the internet)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


# Pattern: EC2 Instance (the actual server)
# This creates a virtual machine in AWS that will run our SENTINEL app.
# t2.micro is in the AWS free tier — no charge for the first 12 months.
resource "aws_instance" "sentinel" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.sentinel.key_name
  vpc_security_group_ids = [aws_security_group.sentinel.id]

  # Pattern: User Data (bootstrap script)
  # This script runs ONCE when the instance first boots up.
  # It installs everything SENTINEL needs: Docker, Python, PostgreSQL client.
  # After this, we just need to SSH in and deploy our code.
  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Update the package list and install dependencies
    apt-get update -y
    apt-get install -y docker.io docker-compose python3-pip python3-venv git

    # Start Docker and enable it to run on boot
    systemctl start docker
    systemctl enable docker

    # Add the default "ubuntu" user to the docker group
    # so we can run docker commands without sudo
    usermod -aG docker ubuntu
  EOF

  # Tag the instance with a name so it's easy to find in the AWS console
  tags = {
    Name    = "sentinel-server"
    Project = "SENTINEL"
  }
}
