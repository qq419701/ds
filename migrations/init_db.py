"""Initialize database and create default admin user."""
from app import create_app
from app.extensions import db
from app.models.user import User


def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()

        # Create default admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                name='超级管理员',
                role='admin',
                can_view_order=1,
                can_deliver=1,
                can_refund=1,
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('Default admin user created: admin / admin123')
        else:
            print('Admin user already exists')

        print('Database initialized successfully')


if __name__ == '__main__':
    init_db()
