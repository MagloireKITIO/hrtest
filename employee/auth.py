from django.contrib.auth import authenticate

def custom_authenticate(request, username=None, password=None):
    user = authenticate(username=username, password=password)
    
    try:
        employee = user.employee_get if user else None
        
        if user and employee:
            # Réinitialiser le compteur en cas de succès
            employee.reset_failed_attempts()
            return user
        else:
            # Trouver l'employé par email pour incrémenter les tentatives
            from employee.models import Employee
            employee = Employee.objects.filter(email=username).first()
            if employee:
                employee.increment_failed_attempts()
                
    except Exception as e:
        # Log l'erreur mais ne pas casser l'authentification
        print(f"Error in custom_authenticate: {e}")
        
    return None