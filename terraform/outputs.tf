# outputs.tf — What Terraform prints after it finishes building
#
# After "terraform apply" creates the EC2 instance, we need to know its IP address
# so we can SSH in and deploy our code. Terraform prints these outputs at the end.

output "instance_public_ip" {
  description = "The public IP of the EC2 instance — use this to SSH in and access the API"
  value       = aws_instance.sentinel.public_ip
}

output "instance_id" {
  description = "The AWS instance ID — useful for debugging in the AWS console"
  value       = aws_instance.sentinel.id
}

output "ssh_command" {
  description = "Copy-paste this to SSH into the server"
  value       = "ssh -i ~/.ssh/sentinel_key ubuntu@${aws_instance.sentinel.public_ip}"
}
