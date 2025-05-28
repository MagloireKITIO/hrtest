import pandas as pd

# Modèle avec les colonnes requises
data = {
    'Department': ['IT', 'HR', 'Finance'],  # Exemples
}

df = pd.DataFrame(data)
df.to_excel('static/templates/department_import_template.xlsx', index=False)