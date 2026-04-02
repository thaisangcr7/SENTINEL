# variables.tf — Configurable values for our infrastructure
#
# Instead of hardcoding things like region and instance size directly in main.tf,
# we define them here as variables. This makes it easy to change values in one place
# and also lets us override them from the command line if needed.

variable "aws_region" {
  description = "Which AWS region to deploy in (us-east-1 = Virginia, cheapest)"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance size — t2.micro is free tier eligible"
  type        = string
  default     = "t2.micro"
}

variable "ssh_public_key_path" {
  description = "Path to your SSH public key so you can log into the server"
  type        = string
  default     = "~/.ssh/sentinel_key.pub"
}
