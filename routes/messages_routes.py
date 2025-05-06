from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_, and_, distinct, func
from sqlalchemy.orm import aliased,  joinedload, selectinload
from app import db 

from models.messages import Conversation, ConversationParticipant, Message
from models.user import User

message_bp = Blueprint('message_bp', __name__, url_prefix='/messages')

@message_bp.route('/conversations', methods=['GET'])
@login_required
def get_user_conversations():
        
    from sqlalchemy.orm import joinedload
    
    current_user_id = current_user.id

    latest_message_subquery = db.session.query(
        Message.conversation_id,
        Message.id.label('last_message_id'),
        Message.content.label('last_message_content'),
        Message.timestamp.label('last_message_timestamp'),
        Message.sender_id.label('last_message_sender_id'),
        func.row_number().over(
            partition_by=Message.conversation_id,
            order_by=Message.timestamp.desc()
        ).label('rn') 
    ).subquery() 

    lm_alias = aliased(latest_message_subquery)

   # Aplicar las opciones de carga PRIMERO
    conversations_query = db.session.query(
        Conversation, # Selecciona el objeto Conversation completo
        lm_alias.c.last_message_id,
        lm_alias.c.last_message_content,
        lm_alias.c.last_message_timestamp,
        lm_alias.c.last_message_sender_id # Incluir el ID del remitente del último mensaje
    )\
    .options(
        # --- Cargar Creador directamente desde Conversation ---
        joinedload(Conversation.creator),

        # --- Cargar Participantes Y el usuario dentro de cada participante desde Conversation ---
        joinedload(Conversation.participants).joinedload(ConversationParticipant.user)
    )\
    .join(ConversationParticipant, Conversation.id == ConversationParticipant.conversation_id)\
    .filter(ConversationParticipant.user_id == current_user_id)\
    .filter(Conversation.deleted_at.is_(None))\
    .outerjoin(lm_alias, and_(
        Conversation.id == lm_alias.c.conversation_id,
        lm_alias.c.rn == 1 # Filtra para unir solo con el último mensaje (rango 1)
    ))\
    .order_by(lm_alias.c.last_message_timestamp.desc().nulls_last()) # Ordena por el timestamp del último mensaje (descendente
    conversations_data = []
    for conv, last_msg_id, last_msg_content, last_msg_timestamp, last_msg_sender_id in conversations_query.all():
        conv_data = conv.serializer() 
        last_message_data = None
        if last_msg_id: 
             last_message_data = {
                 "id": last_msg_id,
                 "content": last_msg_content,
                 "timestamp": last_msg_timestamp.isoformat() if last_msg_timestamp else None,
                 "sender_id": last_msg_sender_id,
             }

        conv_data['last_message'] = last_message_data
        conversations_data.append(conv_data)

    return jsonify(conversations_data), 200


@message_bp.route('/conversations/<int:conversation_id>/messages', methods=['GET'])
@login_required
def get_conversation_messages(conversation_id):
    current_user_id = current_user.id
    is_participant = db.session.query(ConversationParticipant)\
       .filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == current_user_id,
            Conversation.deleted_at.is_(None)
        )\
        .first()

    if not is_participant:
        return jsonify({"message": "Acceso denegado. No eres participante de esta conversación."}), 403 

    messages_query = Message.query.filter_by(conversation_id=conversation_id)\
        .options(joinedload(Message.sender))\
        .order_by(Message.timestamp.asc())
                             
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int) 
        if page < 1: page = 1
        if per_page < 1: per_page = 1
        if per_page > 100: per_page = 100 
    except ValueError:
        return jsonify({"message": "Parámetros de paginación inválidos ('page' o 'per_page' deben ser enteros)."}), 400
      
    messages_query = Message.query.filter_by(conversation_id=conversation_id)\
                                 .order_by(Message.timestamp.asc()) 
    pagination = messages_query.paginate(page=page, per_page=per_page, error_out=False)
    messages_data = [msg.serializer() for msg in pagination.items]
    pagination_metadata = {
        'total_items': pagination.total,
        'total_pages': pagination.pages,
        'current_page': pagination.page,
        'items_per_page': pagination.per_page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
        'next_page': pagination.next_num, 
        'prev_page': pagination.prev_num, 
    }

    return jsonify({
        'messages': messages_data,
        'pagination': pagination_metadata
    }), 200


@message_bp.route('/conversations/<int:conversation_id>/messages', methods=['POST'])
@login_required
def send_message_to_conversation(conversation_id):
   
    current_user_id = current_user.id
    data = request.get_json()

    if not data or 'content' not in data:
        return jsonify({"message": "content es obligatorio en el cuerpo de la petición."}), 400

    content = data['content']

    is_participant = db.session.query(ConversationParticipant)\
        .filter_by(conversation_id=conversation_id, user_id=current_user_id)\
        .first()

    if not is_participant:
        return jsonify({"message": "Acceso denegado. No puedes enviar mensajes a esta conversación."}), 403 

    conversation = Conversation.query.get(conversation_id)
    if not conversation:
         return jsonify({"message": "Conversación no encontrada"}), 404

    new_message = Message(
        sender_id=current_user_id,
        conversation_id=conversation_id,
        content=content
    )

    db.session.add(new_message)

    try:
        db.session.add(new_message) 
        db.session.flush() 
        db.session.commit()
        db.session.refresh(new_message)
        message_to_return = Message.query.options(joinedload(Message.sender)).get(new_message.id)
        return jsonify(message_to_return.serializer()), 201 
    except Exception as e:
        db.session.rollback()
        print(f"Error al guardar el mensaje en la conversación {conversation_id}: {e}")
        return jsonify({"message": "Error al enviar el mensaje.", "details": str(e)}), 500


@message_bp.route('/conversations', methods=['POST'])
@login_required
def create_conversation():
    current_user_id = current_user.id
    data = request.get_json()

    if not data or 'participant_ids' not in data or not isinstance(data['participant_ids'], list):
        return jsonify({"message": "Se espera 'participant_ids' (lista de IDs) en el cuerpo de la petición."}), 400

    participant_ids = list(set(data['participant_ids'])) 
    if current_user_id not in participant_ids:
        participant_ids.append(current_user_id)

    users_to_add = User.query.filter(User.id.in_(participant_ids)).all()
    if len(users_to_add) != len(participant_ids):
        found_ids = {u.id for u in users_to_add}
        missing_ids = list(set(participant_ids) - found_ids)
        return jsonify({"message": f"Algunos IDs de participantes no son válidos: {missing_ids}"}), 400

    conversation_name = data.get('name') 
    new_conversation = Conversation(name=conversation_name,  creator_id=current_user.id)

    db.session.add(new_conversation)
    db.session.flush() 

    participants_associations = []
    for user_obj in users_to_add:
        association = ConversationParticipant(
            conversation_id=new_conversation.id,
            user_id=user_obj.id,
        )
        participants_associations.append(association)
        db.session.add(association) 
        db.session.flush()
    try:
        db.session.commit()
        conversation_to_return = Conversation.query.options(
            joinedload(Conversation.participants).joinedload(ConversationParticipant.user)
        ).get(new_conversation.id)
        
        return jsonify(conversation_to_return.serializer()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear la conversación: {e}")
        return jsonify({"message": "Error al crear la conversación.", "details": str(e)}), 500


@message_bp.route('/users/<int:other_user_id>/conversation', methods=['POST'])
@login_required
def get_or_create_dm_conversation(other_user_id):    
    current_user_id = current_user.id
    if current_user_id == other_user_id:   
        return jsonify({"message": "No puedes crear un DM contigo mismo."}), 400

    other_user = User.query.get(other_user_id)
    if not other_user:
        return jsonify({"message": "El usuario con el que intentas iniciar un DM no fue encontrado."}), 404

    existing_conversation = db.session.query(Conversation)\
        .join(ConversationParticipant, Conversation.id == ConversationParticipant.conversation_id)\
        .filter(ConversationParticipant.user_id.in_([current_user_id, other_user_id]))\
        .group_by(Conversation.id)\
        .having(func.count(ConversationParticipant.user_id) == 2)\
        .first() 
        
    if existing_conversation:
        print(f"DM Conversation already exists between {current_user_id} and {other_user_id}. ID: {existing_conversation.id}")  
        if existing_conversation.deleted_at is not None:
                print(f"Reactivating soft-deleted conversation ID: {existing_conversation.id}")
                existing_conversation.deleted_at = None 
                db.session.add(existing_conversation) 
                current_user_is_participant = db.session.query(ConversationParticipant)\
                    .filter_by(conversation_id=existing_conversation.id, user_id=current_user_id).first()
                if not current_user_is_participant:
                    print(f"Re-adding user {current_user_id} to conversation {existing_conversation.id}") 
                    db.session.add(ConversationParticipant(conversation_id=existing_conversation.id, user_id=current_user_id))
            
                other_user_is_participant = db.session.query(ConversationParticipant)\
                    .filter_by(conversation_id=existing_conversation.id, user_id=other_user_id).first()
                if not other_user_is_participant:
                    print(f"Re-adding user {other_user_id} to conversation {existing_conversation.id}")
                    db.session.add(ConversationParticipant(conversation_id=existing_conversation.id, user_id=other_user_id))

            
                try:
                    db.session.commit()
                    print(f"Conversation {existing_conversation.id} reactivated and participants re-added.") 
                except Exception as e:
                    db.session.rollback()
                    print(f"Error during reactivation commit for conversation {existing_conversation.id}: {e}")
                    return jsonify({"message": "Error al reactivar la conversación.", "details": str(e)}), 500

                conversation_to_return = Conversation.query.options(
                        selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
                        joinedload(Conversation.creator)
                    ).get(existing_conversation.id)

        return jsonify(conversation_to_return.serializer()), 200
    
    print(f"Creating new DM Conversation between {current_user_id} and {other_user_id}")
    try:
   
        new_conversation = Conversation(name=None, creator_id=current_user.id) 
     
        db.session.add(new_conversation)
        db.session.flush() 

        participant1_association = ConversationParticipant(
            conversation_id=new_conversation.id,
            user_id=current_user_id
        )
        participant2_association = ConversationParticipant(
            conversation_id=new_conversation.id,
            user_id=other_user_id
        )

        db.session.add(participant1_association)
        db.session.add(participant2_association)
        db.session.commit()

       
        return jsonify(new_conversation.serializer()), 201 

    except Exception as e:
        db.session.rollback() 
        print(f"Error al crear nuevo DM entre {current_user_id} y {other_user_id}: {e}") 
        return jsonify({"message": "Error interno al crear la conversación.", "details": str(e)}), 500 
    
    
@message_bp.route('/conversations/<int:conversation_id>/participants', methods=['POST'])
@login_required
def manage_participants(conversation_id):
    current_user_id = current_user.id
    data = request.get_json()

    if not data:
        return jsonify({"message": "Cuerpo de petición JSON vacío."}), 400

    add_user_ids = data.get('add', [])
    remove_user_ids = data.get('remove', [])

    if not isinstance(add_user_ids, list) or not isinstance(remove_user_ids, list):
         return jsonify({"message": "Los campos 'add' y 'remove' deben ser listas de IDs de usuario."}), 400

    add_user_ids = set(add_user_ids)
    remove_user_ids = set(remove_user_ids)

    if current_user_id in remove_user_ids:
         return jsonify({"message": "Usa la función de 'salir del grupo' para quitarte a ti mismo."}), 400

    conversation = Conversation.query.filter(
        Conversation.id == conversation_id,
        Conversation.deleted_at.is_(None) 
    ).first()

    if not conversation:
        return jsonify({"message": "Conversación no encontrada."}), 404

    is_current_user_participant = db.session.query(ConversationParticipant)\
        .filter_by(conversation_id=conversation_id, user_id=current_user_id)\
        .first()

    if not is_current_user_participant:
        return jsonify({"message": "No tienes permiso para gestionar participantes en esta conversación."}), 403 

    users_added = []
    if add_user_ids:
        users_to_add_objs = User.query.filter(User.id.in_(add_user_ids)).all()
        found_add_ids = {u.id for u in users_to_add_objs}
        missing_add_ids = add_user_ids - found_add_ids 

        if missing_add_ids:
            return jsonify({"message": f"Error: Algunos IDs de usuarios a añadir no son válidos: {list(missing_add_ids)}"}), 400

        current_participant_ids_query = db.session.query(ConversationParticipant.user_id)\
            .filter_by(conversation_id=conversation_id)
        current_participant_ids = {row[0] for row in current_participant_ids_query}

        for user_obj in users_to_add_objs:
            if user_obj.id not in current_participant_ids:
                new_participant = ConversationParticipant(
                    conversation_id=conversation_id,
                    user_id=user_obj.id
                )
                db.session.add(new_participant)
                users_added.append({"id": user_obj.id, "username": user_obj.username}) 

    users_removed = []
    if remove_user_ids:
        users_to_remove_objs = User.query.filter(User.id.in_(remove_user_ids)).all()
        found_remove_ids = {u.id for u in users_to_remove_objs}
        missing_remove_ids = remove_user_ids - found_remove_ids 

        if missing_remove_ids:
           
            return jsonify({"message": f"Error: Algunos IDs de usuarios a quitar no son válidos: {list(missing_remove_ids)}"}), 400

        current_participants = db.session.query(ConversationParticipant)\
             .filter_by(conversation_id=conversation_id).all()
        current_participant_count = len(current_participants)
        current_participant_ids_map = {p.user_id: p for p in current_participants} 
        participants_remaining_after_removal_count = current_participant_count - len(remove_user_ids.intersection(current_participant_ids_map.keys()))

        if participants_remaining_after_removal_count <= 1 and current_participant_count > 0:
             return jsonify({"message": "No puedes eliminar al último participante de la conversación."}), 400


        for user_id_to_remove in remove_user_ids:
             if user_id_to_remove in current_participant_ids_map:
                 participant_association_to_delete = current_participant_ids_map[user_id_to_remove]
                 db.session.delete(participant_association_to_delete)
                 user_obj_removed = User.query.get(user_id_to_remove) 
                 users_removed.append({"id": user_id_to_remove, "username": user_obj_removed.username if user_obj_removed else None}) 
    try:
        db.session.commit()
        return jsonify({
            "message": "Participantes gestionados exitosamente.",
            "added": users_added,
            "removed": users_removed
        }), 200

    except Exception as e:
        db.session.rollback() 
        print(f"Error during participant management commit for conversation {conversation_id}: {e}")
        return jsonify({"message": "Error al gestionar participantes.", "details": str(e)}), 500
    
    
@message_bp.route('/conversations/<int:conversation_id>/participants/me', methods=['DELETE'])
@login_required
def leave_conversation(conversation_id):
    current_user_id = current_user.id
    participant_association = db.session.query(ConversationParticipant)\
        .filter_by(conversation_id=conversation_id, user_id=current_user_id)\
        .first()

    if not participant_association:   
        return jsonify({"message": "No eres participante de esta conversación."}), 404 

    current_participant_count = db.session.query(func.count(ConversationParticipant.user_id))\
        .filter_by(conversation_id=conversation_id)\
        .scalar() 

    try:
        db.session.delete(participant_association)

        if current_participant_count == 1:
            conversation = Conversation.query.get(conversation_id)
            if conversation:
                conversation.deleted_at = func.now() 
                db.session.add(conversation) 

        db.session.commit()

        if current_participant_count == 1:
             return jsonify({"message": "Saliste de la conversación y la conversación ha sido eliminada."}), 200
        else:
             return jsonify({"message": "Saliste de la conversación exitosamente."}), 200

    except Exception as e:
        db.session.rollback() 
        print(f"Error al intentar salirse de la conversación {conversation_id} para el usuario {current_user_id}: {e}")
        return jsonify({"message": "Error interno al salirse de la conversación.", "details": str(e)}), 


# GET /messages/conversations
# GET /messages/conversations/<int:conversation_id>/messages
# POST /messages/conversations/<int:conversation_id>/messages
# POST /messages/conversations       <-- Creación de grupo (o DM si solo 2 IDs)
# POST /messages/users/<int:other_user_id>/conversation  <-- Creación/Obtención específica de DM 1-a-1