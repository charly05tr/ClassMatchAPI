from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_, and_, distinct, func
from sqlalchemy.orm import aliased,  joinedload, selectinload
from models.user import User
from flask_socketio import emit, join_room, leave_room, disconnect
from app import db, socketio

from models.messages import Conversation, ConversationParticipant, Message
from models.user import User

message_bp = Blueprint('message_bp', __name__, url_prefix='/messages')

# Dictionary to map user_id to a set of active session_ids (handles multiple tabs/devices)
# In production, this should use a shared store like Redis
active_user_sids = {} # {user_id: {sid1, sid2, ...}}
sid_user_map = {} # {sid: user_id}
def get_user_id_from_sid(sid):
    return sid_user_map.get(sid)

# Helper function to get the User object from the session ID
def get_user_from_sid(sid):
    user_id = get_user_id_from_sid(sid)
    if user_id:
        return User.query.get(user_id)
    return None

# @message_bp.route('/conversations', methods=['GET'])
# @login_required
# def get_user_conversations():
        
#     from sqlalchemy.orm import joinedload
    
#     current_user_id = current_user.id

#     latest_message_subquery = db.session.query(
#         Message.conversation_id,
#         Message.id.label('last_message_id'),
#         Message.content.label('last_message_content'),
#         Message.timestamp.label('last_message_timestamp'),
#         Message.sender_id.label('last_message_sender_id'),
#         func.row_number().over(
#             partition_by=Message.conversation_id,
#             order_by=Message.timestamp.desc()
#         ).label('rn') 
#     ).subquery() 

#     lm_alias = aliased(latest_message_subquery)

#    # Aplicar las opciones de carga PRIMERO
#     conversations_query = db.session.query(
#         Conversation, # Selecciona el objeto Conversation completo
#         lm_alias.c.last_message_id,
#         lm_alias.c.last_message_content,
#         lm_alias.c.last_message_timestamp,
#         lm_alias.c.last_message_sender_id # Incluir el ID del remitente del último mensaje
#     )\
#     .options(
#         # --- Cargar Creador directamente desde Conversation ---
#         joinedload(Conversation.creator),

#         # --- Cargar Participantes Y el usuario dentro de cada participante desde Conversation ---
#         joinedload(Conversation.participants).joinedload(ConversationParticipant.user)
#     )\
#     .join(ConversationParticipant, Conversation.id == ConversationParticipant.conversation_id)\
#     .filter(ConversationParticipant.user_id == current_user_id)\
#     .filter(Conversation.deleted_at.is_(None))\
#     .outerjoin(lm_alias, and_(
#         Conversation.id == lm_alias.c.conversation_id,
#         lm_alias.c.rn == 1 # Filtra para unir solo con el último mensaje (rango 1)
#     ))\
#     .order_by(lm_alias.c.last_message_timestamp.desc().nulls_last()) # Ordena por el timestamp del último mensaje (descendente
#     conversations_data = []
#     for conv, last_msg_id, last_msg_content, last_msg_timestamp, last_msg_sender_id in conversations_query.all():
#         conv_data = conv.serializer() 
#         last_message_data = None
#         if last_msg_id: 
#              last_message_data = {
#                  "id": last_msg_id,
#                  "content": last_msg_content,
#                  "timestamp": last_msg_timestamp.isoformat() if last_msg_timestamp else None,
#                  "sender_id": last_msg_sender_id,
#              }

#         conv_data['last_message'] = last_message_data
#         conversations_data.append(conv_data)

#     return jsonify(conversations_data), 200


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
        .filter(Conversation.deleted_at.is_(None))\
        .group_by(Conversation.id)\
        .having(func.count(ConversationParticipant.user_id) == 2)\
        .first() 
    
    if not existing_conversation:
        soft_deleted_dm_candidate = db.session.query(Conversation)\
            .filter(Conversation.deleted_at.isnot(None))\
            .filter(Conversation.name.is_(None))\
            .filter(Conversation.creator_id.in_([current_user_id, other_user_id]))\
            .order_by(Conversation.created_at.desc()).first()
        if soft_deleted_dm_candidate:
            print(f"Found a soft-deleted DM candidate: {soft_deleted_dm_candidate.id}")
            existing_conversation = soft_deleted_dm_candidate
        else:
            print("No soft-deleted DM candidates found.")
            existing_conversation = None 
            
    if existing_conversation:
        print(f"DM Conversation already exists between {current_user_id} and {other_user_id}. ID: {existing_conversation.id}")  
        if existing_conversation.deleted_at is not None:
                print(f"Reactivating soft-deleted conversation ID: {existing_conversation.id}")
                existing_conversation.deleted_at = None 
                db.session.add(existing_conversation) 
                needs_commit_reactivation = True
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
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f'--> CONNECT: Inicio de manejo de conexión para SID: {sid}')
    print(f'request {request}')
    # --- Authentication Logic (Acceder a query parameters) ---
    # Obtén el userId de los query parameters de la URL de conexión
    # request.args es un objeto similar a un diccionario con los query params
    user_id_str = request.args.get('userId')

    authenticated_user_id = None    
    if user_id_str:
        try:
            # Intenta convertir el userId a entero
            user_id_int = int(user_id_str)
            # Opcional: Verificar si este user_id existe en tu base de datos
            # authenticated_user = User.query.get(user_id_int)
            # if authenticated_user:
            #    authenticated_user_id = authenticated_user.id
            # else:
            #    print(f'--> CONNECT: Invalid user ID {user_id_str} from query - User not found.')
            #    emit('status', {'msg': 'Invalid user ID'}, room=sid)
            #    disconnect() # Desconectar si el ID no existe
            #    return # Salir del handler

            # Para simplificar, si el userId está presente y es un entero válido, lo usamos.
            # MEJORA LA SEGURIDAD AQUÍ: Deberías verificar que este userId corresponde a
            # una sesión loggeada REAL (ej. comparando con la sesión HTTP asociada si usas cookies,
            # o verificando un token si usas autenticación por token).
            authenticated_user_id = user_id_int
            print(f'--> CONNECT: Recibido y validado User ID desde query: {authenticated_user_id}')

        except ValueError:
            print(f'--> CONNECT: User ID inválido (no es entero) desde query: {user_id_str}')
            emit('status', {'msg': 'Invalid user ID format'}, room=sid)
            # disconnect() # Desconectar si el formato es incorrecto
            return


    if authenticated_user_id:
        print(f'--> CONNECT: Usuario autenticado (vía query param): {authenticated_user_id}')
        user_id = authenticated_user_id # Usar el ID autenticado

        # Store the mapping
        if user_id not in active_user_sids:
            active_user_sids[user_id] = set()
        active_user_sids[user_id].add(sid)
        sid_user_map[sid] = user_id

        # Join the user's personal room
        join_room(f'user_{user_id}')
        print(f'--> CONNECT: User {user_id} ({sid}) agregado a active_user_sids y unido a room user_{user_id}')

        emit('status', {'msg': 'Connected successfully!', 'user_id': user_id}, room=sid)
        print(f'--> CONNECT: Emitido status al cliente {sid}')
    else:
        print(f'--> CONNECT: Cliente no autenticado (userId faltante en query). SID: {sid}')
        emit('status', {'msg': 'Authentication required (userId missing).'}, room=sid)
        # Optional: Disconnect unauthenticated clients immediately
        # disconnect()
        print(f'--> CONNECT: Emitido status y/o desconectando cliente no autenticado {sid}')

    print(f'--> CONNECT: Fin de manejo de conexión para SID: {sid}')


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    user_id = sid_user_map.get(sid) # Get user_id from our mapping

    if user_id:
        print(f'--> DISCONNECT: User {user_id} disconnected via WebSocket: {sid}')
        # Remove the mapping
        if user_id in active_user_sids and sid in active_user_sids[user_id]:
            active_user_sids[user_id].remove(sid)
            if not active_user_sids[user_id]: # Remove user entry if no active SIDs
                del active_user_sids[user_id]
        del sid_user_map[sid]

        # Leave the user's personal room
        leave_room(f'user_{user_id}')
        print(f'--> DISCONNECT: Client {sid} left personal room user_{user_id}')

    else:
        print(f'--> DISCONNECT: Unauthenticated client disconnected: {sid}')

# Handler for client joining a specific conversation room
@socketio.on('join_conversation')
# REMOVE @login_required here
def on_join_conversation(data):
    sid = request.sid
    print(sid)
    user_id = get_user_id_from_sid(sid) # Get user ID from our mapping

    if not user_id:
         print(f'--> JOIN_CONV: Cliente no autenticado {sid} intentó unirse a room.')
         emit('error', {'message': 'Authentication required'}, room=sid)
         # Optionally disconnect if they shouldn't be sending events unauthenticated
         # disconnect()
         return

    conversation_id = data.get('conversation_id')
    print(f'--> JOIN_CONV: Recibido join_conversation de User {user_id} ({sid}) para conv_id: {conversation_id}')


    if not conversation_id:
        print(f'--> JOIN_CONV: User {user_id} ({sid}) sent join_conversation without conversation_id')
        emit('error', {'message': 'conversation_id is required'}, room=sid)
        return

    # --- Verification: Ensure user is a participant in this conversation ---
    is_participant = db.session.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()

    if is_participant:
        room = f'conversation_{conversation_id}'
        # Check if user is already in the room (optional, join_room is safe)
        # if room not in rooms(sid):
        join_room(room)
        print(f'--> JOIN_CONV: EXITO: User {user_id} ({sid}) se unió a la room {room}')
        # Optional: Notify other participants in the room that this user joined (for status)
        # Only emit to others, not the sender (include_self=False)
        emit('user_joined_conv', {'user_id': user_id, 'conversation_id': conversation_id}, room=room, include_self=False)
        emit('joined_conversation', {'conversation_id': conversation_id}, room=sid) # Confirm join to sender
    else:
        print(f'--> JOIN_CONV: FALLO: User {user_id} ({sid}) intentó unirse a room NO AUTORIZADA {f"conversation_{conversation_id}"}. No es participante.')
        emit('error', {'message': 'Unauthorized to join this conversation room'}, room=sid)


# Handler for client leaving a specific conversation room
@socketio.on('leave_conversation')
# REMOVE @login_required here
def on_leave_conversation(data):
    sid = request.sid
    user_id = get_user_id_from_sid(sid) # Get user ID from our mapping

    if not user_id:
         print(f'--> LEAVE_CONV: Cliente no autenticado {sid} intentó salir de room.')
         emit('error', {'message': 'Authentication required'}, room=sid)
         # optionally disconnect
         # disconnect()
         return

    conversation_id = data.get('conversation_id')
    print(f'--> LEAVE_CONV: Recibido leave_conversation de User {user_id} ({sid}) para conv_id: {conversation_id}')

    if not conversation_id:
        print(f'--> LEAVE_CONV: User {user_id} ({sid}) sent leave_conversation without conversation_id')
        emit('error', {'message': 'conversation_id is required'}, room=sid)
        return

    room = f'conversation_{conversation_id}'
    # Check if user is actually in the room before leaving (optional, leave_room is safe)
    # if room in rooms(sid):
    leave_room(room)
    print(f'--> LEAVE_CONV: User {user_id} ({sid}) left room {room}')
    # Optional: Notify other participants that this user left
    emit('user_left_conv', {'user_id': user_id, 'conversation_id': conversation_id}, room=room, include_self=False)


# --- REST API Routes ---

# Endpoint to get conversations for the logged-in user
@message_bp.route('/conversations', methods=['GET'])
@login_required
def get_user_conversations():
    user_id = current_user.id

    try:
        # Query for conversations the user is a participant in
        # Order by the timestamp of the LAST message (descending) or conversation creation date
        # Use a subquery to find the latest message timestamp efficiently
        latest_message_subquery = db.session.query(
            Message.conversation_id,
            db.func.max(Message.timestamp).label('last_message_timestamp')
        ).group_by(Message.conversation_id).subquery()

        conversations_query = db.session.query(Conversation)\
            .join(ConversationParticipant)\
            .filter(ConversationParticipant.user_id == user_id)\
            .filter(Conversation.deleted_at.is_(None))\
            .options(joinedload(Conversation.participants).joinedload(ConversationParticipant.user))\
            .options(joinedload(Conversation.creator))\
            .outerjoin(latest_message_subquery, latest_message_subquery.c.conversation_id == Conversation.id)\
            .order_by(db.desc(latest_message_subquery.c.last_message_timestamp), db.desc(Conversation.created_at)) # Order by last message timestamp or creation date

        # --- Pagination (Optional but Recommended) ---
        # page = request.args.get('page', 1, type=int)
        # per_page = request.args.get('per_page', 20, type=int)
        # paginated_convs = conversations_query.paginate(page=page, per_page=per_page, error_out=False)
        # conversations_list = paginated_convs.items
        # pagination_info = { ... }

        conversations_list = conversations_query.all() # For simplicity, fetch all for now

        # Fetch the last message for each conversation for serialization
        # This can still be an N+1 issue if not optimized further (e.g., using window functions or joining last message in the main query)
        # For now, fetch them individually:
        conversations_with_last_message = []
        for conv in conversations_list:
             last_message = Message.query.filter_by(conversation_id=conv.id)\
                                .order_by(Message.timestamp.desc())\
                                .options(joinedload(Message.sender))\
                                .first()
             conv_data = conv.serializer()
             conv_data['last_message'] = last_message.serializer() if last_message else None
             conversations_with_last_message.append(conv_data)


        return jsonify(conversations_with_last_message), 200

    except Exception as e:
        print(f"Error fetching conversations: {e}")
        db.session.rollback() # Ensure rollback in case of query errors
        return jsonify({"message": "Internal server error while fetching conversations"}), 500


# Endpoint to get messages for a specific conversation
@message_bp.route('/conversations/<int:conversation_id>/messages', methods=['GET'])
@login_required
def get_conversation_messages(conversation_id):
    user_id = current_user.id

    # Verify user is a participant
    is_participant = db.session.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()

    if not is_participant:
        return jsonify({"message": "Unauthorized access to conversation"}), 403

    try:
        # Get messages with pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)

        messages_query = Message.query.filter_by(conversation_id=conversation_id)\
                                    .order_by(Message.timestamp.asc())\
                                    .options(joinedload(Message.sender)) # Eager load sender

        paginated_messages = messages_query.paginate(page=page, per_page=per_page, error_out=False)

        serialized_messages = [msg.serializer() for msg in paginated_messages.items]

        pagination_info = {
            "total_items": paginated_messages.total,
            "total_pages": paginated_messages.pages,
            "current_page": paginated_messages.page,
            "items_per_page": paginated_messages.per_page,
            "has_next": paginated_messages.has_next,
            "has_prev": paginated_messages.prev_num,
            "next_page": paginated_messages.next_num,
            "prev_page": paginated_messages.prev_num,
        }

        return jsonify({"messages": serialized_messages, "pagination": pagination_info}), 200

    except Exception as e:
        print(f"Error fetching messages: {e}")
        db.session.rollback() # Rollback in case of query errors
        return jsonify({"message": "Internal server error while fetching messages"}), 500


# Endpoint to send a message
@message_bp.route('/conversations/<int:conversation_id>/messages', methods=['POST'])
@login_required
def send_message(conversation_id):
    user_id = current_user.id
    data = request.get_json()
    content = data.get('content')

    if not content or not isinstance(content, str) or not content.strip():
        return jsonify({"message": "Message content is required"}), 400

    # Verify user is a participant
    is_participant = db.session.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()

    if not is_participant:
        return jsonify({"message": "Unauthorized to send message to this conversation"}), 403

    try:
        # 1. Save the message to the database
        new_message = Message(
            sender_id=user_id,
            conversation_id=conversation_id,
            content=content.strip()
            # timestamp is auto-generated by server_default
        )
        db.session.add(new_message)
        db.session.commit() # Commit to get the message ID and timestamp

        # Refresh or get the message again to ensure relationships (sender) and DB-generated fields are loaded
        # Or load with joinedload specifically
        message_to_emit = db.session.query(Message)\
                                   .options(joinedload(Message.sender))\
                                   .get(new_message.id)


        # 2. Broadcast the new message via SocketIO
        # Emit the 'new_message' event to the conversation's room
        serialized_message_data = message_to_emit.serializer()

        print(f"Emitting new_message for conv {conversation_id} to room conversation_{conversation_id}")
        socketio.emit('new_message', serialized_message_data, room=f'conversation_{conversation_id}')

        # 3. Return success response (return the serialized data including sender, timestamp, etc.)
        return jsonify(serialized_message_data), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error sending message: {e}")
        return jsonify({"message": "Internal server error while sending message"}), 500


# Endpoint to create a new conversation (DM or Group)
# Accepts participant_ids (list of user IDs) and optional 'name'
@message_bp.route('/conversations', methods=['POST'])
@login_required
def create_conversation():
    user_id = current_user.id
    data = request.get_json()
    name = data.get('name') # Optional name for groups
    participant_ids = data.get('participant_ids') # List of user IDs

    if not isinstance(participant_ids, list) or not participant_ids:
        return jsonify({"message": "Participant IDs are required and must be a list"}), 400

    # Ensure participant IDs are integers
    try:
        participant_ids = [int(pid) for pid in participant_ids]
    except ValueError:
        return jsonify({"message": "Participant IDs must be integers"}), 400

    # Ensure current user is in the participant list (backend validation)
    if user_id not in participant_ids:
        participant_ids.append(user_id)

    # Remove duplicates just in case
    participant_ids = list(set(participant_ids))


    # Validate participant IDs exist
    users = User.query.filter(User.id.in_(participant_ids)).all()
    if len(users) != len(participant_ids):
         # Find missing IDs for a more specific error
         existing_ids = [u.id for u in users]
         missing_ids = list(set(participant_ids) - set(existing_ids))
         return jsonify({"message": f"Invalid participant ID(s) provided: {missing_ids}"}), 400

    # Validate min participants (at least creator + 1 other = minimum 2 unique IDs including creator)
    if len(participant_ids) < 2:
        # This case should technically not happen if frontend validates, but good backend defense
        return jsonify({"message": "A conversation must have at least two unique participants."}), 400

    # Handle DM vs Group logic
    if name is None and len(participant_ids) == 2:
        # It's a potential DM. Check if an active DM already exists.
        other_user_id = [pid for pid in participant_ids if pid != user_id]
        if not other_user_id: # Should not happen if len(participant_ids) == 2 and user_id is in list
             return jsonify({"message": "Could not determine other participant for DM."}), 500
        other_user_id = other_user_id[0] # Get the single other user ID

        # Find existing DM by checking conversations with exactly 2 participants being user_id and other_user_id, no name, not deleted
        existing_dm = db.session.query(Conversation)\
            .join(ConversationParticipant)\
            .group_by(Conversation.id)\
            .having(
                # Count exactly 2 participants
                db.func.count(ConversationParticipant.user_id) == 2
            )\
            .filter(Conversation.name.is_(None))\
            .filter(Conversation.deleted_at.is_(None))\
            .filter(
                 # Ensure the *exact* two participants are user_id and other_user_id
                 and_(
                     db.session.query(db.func.count(ConversationParticipant.user_id))\
                         .filter(ConversationParticipant.conversation_id == Conversation.id, ConversationParticipant.user_id == user_id)\
                         .scalar() == 1,
                      db.session.query(db.func.count(ConversationParticipant.user_id))\
                         .filter(ConversationParticipant.conversation_id == Conversation.id, ConversationParticipant.user_id == other_user_id)\
                         .scalar() == 1
                 )
             )\
             .options(joinedload(Conversation.participants).joinedload(ConversationParticipant.user))\
             .options(joinedload(Conversation.creator))\
            .first() # Find the first match

        if existing_dm:
            print(f"Existing DM found between {user_id} and {other_user_id}: {existing_dm.id}")
            # Return the existing conversation
            # TODO: Consider if the frontend needs a specific status code like 200 instead of 201
            # to indicate "found existing" vs "created new". For now, returning 200 with existing data.
            # The frontend expects the conversation object either way.
            return jsonify(existing_dm.serializer()), 200 # Return 200 OK for existing

    # If it's a new DM or a Group
    try:
        new_conversation = Conversation(
            name=name.strip() if name else None, # Store empty string as None
            creator_id=user_id if name else None # Only set creator for groups (optional, could be null for DM)
            # created_at is auto-generated
            # deleted_at is initially None
        )
        db.session.add(new_conversation)
        db.session.flush() # Get the new conversation ID before committing

        # Add participants
        for pid in participant_ids:
            participant = ConversationParticipant(
                conversation_id=new_conversation.id,
                user_id=pid
                # joined_at is auto-generated
            )
            db.session.add(participant)

        db.session.commit()

        # Fetch the newly created conversation with participants and creator loaded for serialization
        created_conv = db.session.query(Conversation)\
            .options(joinedload(Conversation.participants).joinedload(ConversationParticipant.user))\
            .options(joinedload(Conversation.creator))\
            .get(new_conversation.id)

        # --- WebSocket Notification for New Conversation ---
        # This is important so clients (participants) see the new conversation appear in their list in real-time
        # Emit to each participant's personal room
        serialized_conv_data = created_conv.serializer()
        for participant in created_conv.participants:
             participant_user_id = participant.user_id
             # Only emit if the participant is not the current user who initiated creation
             # The initiator will likely fetch/select it after the REST response anyway
             # Or emit to all including initiator for consistency
             print(f"Emitting new_conversation to user room user_{participant_user_id}")
             socketio.emit('new_conversation', serialized_conv_data, room=f'user_{participant_user_id}')


        return jsonify(created_conv.serializer()), 201 # Return 201 Created for new

    except Exception as e:
        db.session.rollback()
        print(f"Error creating conversation: {e}")
        return jsonify({"message": "Internal server error while creating conversation"}), 500


# Endpoint for a user to leave a conversation (delete their participation record)
@message_bp.route('/conversations/<int:conversation_id>/participants/me', methods=['DELETE'])
@login_required
def leave_conversation_route(conversation_id): # Renamed to avoid conflict with socketio handler
    user_id = current_user.id

    try:
        # Verify user is a participant and get the participation entry
        participant_entry = db.session.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id
        ).first()

        if not participant_entry:
            return jsonify({"message": "You are not a participant of this conversation"}), 404

        # Delete the participant entry
        db.session.delete(participant_entry)

        # Optional: If it was the last participant in a group, maybe delete the conversation?
        # Check remaining participants in the conversation
        remaining_participants_count = db.session.query(ConversationParticipant)\
            .filter(ConversationParticipant.conversation_id == conversation_id)\
            .count()

        # If no participants left, you might want to delete the conversation itself (cascade handles messages)
        if remaining_participants_count == 0:
             conv_to_delete = Conversation.query.get(conversation_id)
             if conv_to_delete:
                  db.session.delete(conv_to_delete)
                  print(f"Conversation {conversation_id} deleted as last participant left.")
                  # TODO: Emit a WebSocket event to potentially notify anyone *else* somehow tracking this conv
                  # (e.g., other users who were participants before but left earlier) - complex!
             else:
                  # This case should be rare if participant_entry existed
                  print(f"Warning: Participant entry existed for conversation {conversation_id}, but conversation not found.")


        db.session.commit()

        # --- WebSocket Notification for Leaving ---
        # Notify other participants in the conversation's room that this user left
        # This requires getting the conversation object to emit to its room
        # We need to emit *before* the potential conversation delete if we want to use the room
        # Let's refetch the conversation to get its ID for the room name, even if it's about to be deleted
        # Or, save the room name before deleting the participant
        room_to_notify = f'conversation_{conversation_id}'
        # Emit the event. Consider who needs to receive this (only others in the room)
        # The user who left doesn't need to receive this specific event.
        socketio.emit('user_left_conversation', {'user_id': user_id, 'conversation_id': conversation_id}, room=room_to_notify, include_self=False)

        # If the conversation was deleted entirely, maybe send a different event?
        if remaining_participants_count == 0:
             socketio.emit('conversation_deleted', {'conversation_id': conversation_id}, room=room_to_notify, include_self=False) # Notify others in the room

        return jsonify({"message": "Successfully left conversation"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error leaving conversation: {e}")
        return jsonify({"message": "Internal server error while leaving conversation"}), 500


# Endpoint to search for users (for DM and Group forms)
# Assuming this is separate from messages blueprint or handled elsewhere
# Example basic search endpoint:
@message_bp.route('/users/search', methods=['GET']) # Or define in a users_bp
@login_required
def search_users():
    term = request.args.get('term', '')
    if not term:
        return jsonify([])

    # Search users by username or other relevant fields
    # Exclude the current user from results
    search_results = User.query.filter(
        User.id != current_user.id,
        or_(
            User.username.ilike(f'%{term}%'), # Case-insensitive search
            User.name.ilike(f'%{term}%'),
            User.profesion.ilike(f'%{term}%') # Searching profession as requested in frontend
            # Add other searchable fields like first_name, email (carefully)
        )
    ).limit(20).all() # Limit results

    # Serialize results
    serialized_results = [user.serializer() for user in search_results]

    return jsonify(serialized_results), 200


# Example of how to register the blueprint in app.py or __init__.py
# from .routes.messages import messages_bp
# app.register_blueprint(messages_bp)

# Remember to also import and configure Flask-Login and SQLAlchemy in app.py
# and run your app using socketio.run(app)