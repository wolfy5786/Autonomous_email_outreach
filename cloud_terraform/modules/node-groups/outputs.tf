output "node_group_name" {
  value = aws_eks_node_group.app.node_group_name
}

output "node_role_arn" {
  value = aws_iam_role.node.arn
}
