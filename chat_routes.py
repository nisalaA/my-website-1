from flask import Blueprint, jsonify, request, Response, stream_with_context
from flask_login import current_user, login_required
from models import db, ChatMessage, User
import json
from datetime import datetime
import time

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/api/chat/send', methods=['POST'])
@login_required
def send_message():
    data = request.get_json()
    message_content = data.get('message')
    
    if not message_content:
        return jsonify({'error': 'Message content is required'}), 400
    
    # Save user message
    user_message = ChatMessage(
        user_id=current_user.id,
        content=message_content,
        is_from_user=True,
        requires_admin_attention=True
    )
    db.session.add(user_message)
    db.session.commit()
    
    return jsonify({
        'user_message': user_message.to_dict()
    })

@chat_bp.route('/api/chat/stream')
@login_required
def stream_messages():
    last_id = request.args.get('last_id', 0, type=int)
    
    def generate():
        current_id = last_id
        while True:
            # Query for new messages
            messages = ChatMessage.query.filter(
                ChatMessage.user_id == current_user.id,
                ChatMessage.id > current_id
            ).order_by(ChatMessage.id.asc()).all()
            
            if messages:
                current_id = messages[-1].id
                data = json.dumps({
                    'messages': [msg.to_dict() for msg in messages]
                })
                yield f"data: {data}\n\n"
            
            time.sleep(0.5)  # Check every 0.5 seconds
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream'
    )

@chat_bp.route('/api/admin/stream')
@login_required
def admin_stream():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    last_id = request.args.get('last_id', 0, type=int)
    
    def generate():
        current_id = last_id
        while True:
            # Query for new messages requiring admin attention
            messages = ChatMessage.query.filter(
                ChatMessage.id > current_id,
                ChatMessage.requires_admin_attention == True,
                ChatMessage.is_handled == False
            ).order_by(ChatMessage.id.asc()).all()
            
            if messages:
                current_id = messages[-1].id
                # Group messages by user
                users_with_messages = {}
                for message in messages:
                    user = User.query.get(message.user_id)
                    if user:
                        if user.id not in users_with_messages:
                            users_with_messages[user.id] = {
                                'user_id': user.id,
                                'username': user.username,
                                'message': message.to_dict()
                            }
                
                if users_with_messages:
                    data = json.dumps({
                        'users': list(users_with_messages.values())
                    })
                    yield f"data: {data}\n\n"
            
            # Also check for admin responses to current chat
            if request.args.get('current_chat_user'):
                current_chat_user = int(request.args.get('current_chat_user'))
                admin_messages = ChatMessage.query.filter(
                    ChatMessage.id > current_id,
                    ChatMessage.user_id == current_chat_user,
                    ChatMessage.is_from_user == False
                ).order_by(ChatMessage.id.asc()).all()
                
                if admin_messages:
                    current_id = max(current_id, admin_messages[-1].id)
                    data = json.dumps({
                        'admin_messages': [msg.to_dict() for msg in admin_messages]
                    })
                    yield f"data: {data}\n\n"
            
            time.sleep(0.5)  # Check every 0.5 seconds
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream'
    )

@chat_bp.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history():
    messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.timestamp).all()
    return jsonify([msg.to_dict() for msg in messages])

@chat_bp.route('/api/admin/pending-messages', methods=['GET'])
@login_required
def get_pending_messages():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    users_with_messages = db.session.query(User).join(ChatMessage).filter(
        ChatMessage.requires_admin_attention == True,
        ChatMessage.is_handled == False
    ).distinct().all()
    
    result = []
    for user in users_with_messages:
        latest_message = ChatMessage.query.filter_by(
            user_id=user.id,
            requires_admin_attention=True,
            is_handled=False
        ).order_by(ChatMessage.timestamp.desc()).first()
        
        if latest_message:
            result.append({
                'user_id': user.id,
                'username': user.username,
                'message': latest_message.to_dict()
            })
    
    return jsonify(result)

@chat_bp.route('/api/admin/user-chat/<int:user_id>', methods=['GET'])
@login_required
def get_user_chat(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    messages = ChatMessage.query.filter_by(user_id=user_id).order_by(ChatMessage.timestamp).all()
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username
        },
        'messages': [msg.to_dict() for msg in messages]
    })

@chat_bp.route('/api/admin/respond', methods=['POST'])
@login_required
def admin_respond():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    response = data.get('response')
    
    if not user_id or not response:
        return jsonify({'error': 'User ID and response are required'}), 400
    
    # Mark all unhandled messages from this user as handled
    unhandled_messages = ChatMessage.query.filter_by(
        user_id=user_id,
        requires_admin_attention=True,
        is_handled=False
    ).all()
    
    for message in unhandled_messages:
        message.is_handled = True
    
    # Create admin's response message
    admin_message = ChatMessage(
        user_id=user_id,
        content=response,
        is_from_user=False,
        requires_admin_attention=False,
        is_handled=True
    )
    
    db.session.add(admin_message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': admin_message.to_dict()
    })
