from jinja2 import Environment, FileSystemLoader
import os

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader(['templates', '.']))

# List of templates to render
templates = [
    'index.html',
    'login.html',
    'admin_dashboard.html',
    'employee_dashboard.html',
    'customer_dashboard.html',
    'department_dashboard.html'
]

# Output directory
output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)

# Render each template
for template_name in templates:
    template = env.get_template(template_name)
    rendered = template.render()  # Add context here if needed

    output_path = os.path.join(output_dir, template_name)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rendered)

print("Static HTML files generated in 'output/' folder.")
