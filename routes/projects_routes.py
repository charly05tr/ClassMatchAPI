from models.user import User
from flask import Blueprint, jsonify, request
from flask_login import  login_required, current_user
from sqlalchemy import or_, and_
from app import db 
from models.project import Project
from models.asociation import ProjectUserAssociation

project_bp = Blueprint('project_bp', __name__, url_prefix='/projects')

@project_bp.route("/user_projects/<int:user_id>", methods=["GET", "PUT"])
@login_required
def user_projects(user_id):

    user = User.query.get(user_id)

    if request.method == "GET":
        projects_list = []
        
        for association in user.project_associations:
            if association.project:
                project_data = association.project.serializer()
                projects_list.project_bpend(project_data)

        return jsonify(projects_list), 200

    elif request.method == "PUT" and current_user.id == user_id:
        data = request.get_json()
        if not data or 'projects' not in data or not isinstance(data['projects'], list):
            return jsonify({"error": "Formato de datos incorrecto. Se espera un objeto con una clave 'projects' que contenga una lista."}), 400
        incoming_projects_data = data['projects']

        current_associations_map = {assoc.project_id: assoc for assoc in user.project_associations if assoc.project}
        incoming_project_ids = set()

        for project_data in incoming_projects_data:
            if not isinstance(project_data, dict):
                print(f"Advertencia: Skipping invalid item in incoming projects list: {project_data}")
                continue

            project_id = project_data.get('id')
            if project_id is not None and project_id in current_associations_map:
                association_obj = current_associations_map[project_id]
                project_obj = association_obj.project 

                incoming_project_ids.add(project_id)

                project_update_map = {
                    'project_name': 'project_name',
                    'description': 'description',
                    'tecnologies': 'tecnologies',
                    'preview_url': 'preview_url',
                    'code_url': 'code_url',
                    'project_image': 'project_image',
                }

                not_null_fields = ['project_name', 'description'] 

                is_update_valid = True 

                for incoming_key, backend_attr in project_update_map.items():
                  
                    if incoming_key in project_data:
                         value = project_data.get(incoming_key) 

                         if backend_attr in not_null_fields and value is None:
                              
                              print(f"Error de validación: Received null value for required field '{incoming_key}' (maps to '{backend_attr}') for project ID {project_id}.")
                              is_update_valid = False    
                              break
                         if is_update_valid:
                            setattr(project_obj, backend_attr, value)
                if is_update_valid:
                    db.session.add(project_obj)
                    db.session.add(association_obj) 
                else:  
                    pass 
            else: 
                required_fields_new = ["name", "description", "tecnologies"]
                
                if not all(field in project_data and project_data.get(field) is not None for field in required_fields_new):
                    print(f"Warning: Skipping creation of new project due to missing or null required fields: {project_data}")
                    continue 

                new_project = Project(
                    project_name=project_data.get('name'),
                    description=project_data.get('description'),
                    tecnologies=project_data.get('tecnologies'), 
                    preview_url=project_data.get('url_preview'),
                    code_url=project_data.get('url_code'),
                    project_image=project_data.get('image')
                    
                )
                new_association = ProjectUserAssociation(
                    user=user,
                    project=new_project,
                    is_owner=True,
                    is_collaborator=False
                )
                db.session.add(new_project)
                db.session.add(new_association)

        project_ids_to_delete = [
             project_id for project_id in current_associations_map.keys()
             if project_id not in incoming_project_ids
        ]

        for project_id_to_delete in project_ids_to_delete:
            
             association_to_delete = current_associations_map[project_id_to_delete]

             project_obj_to_delete = association_to_delete.project
             if project_obj_to_delete: 
                 db.session.delete(project_obj_to_delete)
         
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback() 
            print(f"Error during project save commit for user {user.id}: {e}")

            return jsonify({"error": "Error al guardar los proyectos en la base de datos.", "details": str(e)}), 500 

        db.session.refresh(user)
       
        profile_data_with_projects = user.serializer()

        return jsonify(profile_data_with_projects), 200 