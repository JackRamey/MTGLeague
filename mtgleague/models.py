from datetime import datetime, date
from flask import url_for
from markupsafe import Markup
from sqlalchemy import or_, and_

from flask_login import AnonymousUserMixin, UserMixin, current_user

from mtgleague.util import bcrypt, db, login_manager, login_serializer


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'))
    participants = db.relationship('Participant', backref='event',
                                   lazy='dynamic')
    stages = db.relationship('Stage', backref='event', lazy='dynamic')

    def __init__(self, name, league):
        self.name = name
        self.league_id = league.id

    def add_participant(self, user):
        participant = Participant(user, self)
        db.session.add(participant)
        db.session.commit()

    def get_start_date(self):
        first_stage = self.stages.order_by(Stage.start_date).first()
        return first_stage.start_date

    def get_end_date(self):
        last_stage = self.stages.order_by(Stage.start_date.desc()).first()
        return last_stage.end_date

    def is_participant(self, user):
        return self.participants.filter_by(user=user).first() is not None

    def is_past(self):
        last_stage = self.stages.order_by(Stage.start_date.desc()).first()
        return last_stage.end_date <= date.today()

    def in_progress(self):
        first_stage = self.stages.order_by(Stage.start_date).first()
        last_stage = self.stages.order_by(Stage.start_date.desc()).first()
        return first_stage.start_date <= date.today() <= last_stage.end_date

    def is_upcoming(self):
        first_stage = self.stages.order_by(Stage.start_date).first()
        return date.today() <= first_stage.start_date

    def __html__(self):
        return Markup('<a href="' + url_for('event', eid=self.id) + '">' + self.name + '</a>')

    def __repr__(self):
        return '<{0}: {1}, {2}>'.format(self.__class__.__name__, self.name, self.league)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name


class League(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    creation_date = db.Column(db.Date)

    events = db.relationship('Event', backref='league', lazy='dynamic')
    members = db.relationship('Membership', backref='league', lazy='dynamic')
    post = db.relationship('Post', backref='league', lazy='dynamic')

    def __init__(self, name, creator):
        self.name = name
        self.creator = creator
        self.creation_date = date.today()

    def add_member(self, user):
        membership = Membership(user, self)
        db.session.add(membership)
        db.session.commit()

    def add_moderator(self, user):
        membership = Membership.query.filter(and_(Membership.league_id == self.id, Membership.user == user)).first()
        membership.moderator = True
        membership.owner = False
        db.session.commit()

    def add_owner(self, user):
        membership = Membership.query.filter(and_(Membership.league_id == self.id, Membership.user == user)).first()
        membership.moderator = False
        membership.owner = True
        db.session.commit()

    def add_post(self, user, title, body):
        post = Post(self, user, title, body)
        db.session.add(post)
        db.session.commit()

    def editable_by_user(self, user):
        return user.id == self.creator_id or user in self.get_moderators()

    def get_members(self):
        return [member.user for member in self.members]

    def get_moderators(self):
        moderators = Membership.query.filter(and_(Membership.league_id == self.id, Membership.moderator)).all()
        return [moderator.user for moderator in moderators]

    def get_owners(self):
        owners = Membership.query.filter(and_(Membership.league_id == self.id, Membership.owner)).all()
        return [owner.user for owner in owners]

    def current_events(self):
        return [event for event in self.events.all() if event.in_progress()]

    def past_events(self):
        return [event for event in self.events.all() if event.is_past()]

    def upcoming_events(self):
        return [event for event in self.events.all() if event.is_upcoming()]

    def __html__(self):
        return Markup('<a href="' + url_for('league', lid=self.id) + '">' + self.name + '</a>')

    def __repr__(self):
        return '<{0}: {1}, {2}>'.format(self.__class__.__name__, self.id, self.name)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey('stage.id'))
    p1_id = db.Column(db.Integer, db.ForeignKey('participant.id'))
    p2_id = db.Column(db.Integer, db.ForeignKey('participant.id'))
    winner_id = db.Column(db.Integer, db.ForeignKey('participant.id'))
    loser_id = db.Column(db.Integer, db.ForeignKey('participant.id'))
    p1_wins = db.Column(db.Integer)
    p2_wins = db.Column(db.Integer)
    draws = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime)

    participant1 = db.relationship('Participant', foreign_keys=[p1_id])
    participant2 = db.relationship('Participant', foreign_keys=[p2_id])
    winner = db.relationship('Participant', foreign_keys=[winner_id])
    loser = db.relationship('Participant', foreign_keys=[loser_id])

    def __init__(self, stage, participant1, participant2):
        self.stage = stage
        self.participant1 = participant1
        self.participant2 = participant2

    def add_results(self, p1_wins=0, p2_wins=0, draws=0):
        pass
        self.p1_wins = p1_wins
        self.p2_wins = p2_wins
        self.draws = draws
        self.timestamp = datetime.now()
        if p1_wins >= 2:
            # set p1 as winner
            self.winner = self.participant1
            self.loser = self.participant2
        if p2_wins >= 2:
            # set p2 as winner
            self.winner = self.participant2
            self.loser = self.participant1
        db.session.commit()


class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'))
    moderator = db.Column(db.Boolean)
    owner = db.Column(db.Boolean)

    def __init__(self, user, league, moderator=False, owner=False):
        self.user = user
        self.league = league
        self.moderator = moderator
        self.owner = owner


class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))

    def __init__(self, user, event):
        self.user = user
        self.event = event

    def get_matches(self):
        return Match.query.filter(or_(Match.p1_id == self.id, Match.p2_id == self.id)).all()

    def get_matches_count(self):
        return Match.query.filter(or_(Match.p1_id == self.id, Match.p2_id == self.id)).count()

    def get_matches_won(self):
        return Match.query.filter_by(winner_id=self.id).all()

    def get_matches_won_count(self):
        return Match.query.filter_by(winner_id=self.id).count()

    def get_matches_lost(self):
        return Match.query.filter_by(loser_id=self.id).all()

    def get_matches_lost_count(self):
        return Match.query.filter_by(loser_id=self.id).count()

    def match_win_percentage(self):
        matches_won = self.get_matches_won_count()
        matches_total = self.get_matches_count()
        return matches_won / matches_total

    def opponent_match_win_percentage(self):
        pass

    def __str__(self):
        return str(self.user)

    def __html__(self):
        return Markup('<a href="' + url_for('participant', pid=self.id) + '">' + self.user.name + '</a>')


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    league_id = db.Column(db.Integer, db.ForeignKey('league.id'))
    title = db.Column(db.String(140))
    body = db.Column(db.String(1000))

    def __init__(self, league, author, title, body):
        self.league = league
        self.author = author
        self.title = title
        self.body = body
        self.created_at = datetime.now()


class Stage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    matches = db.relationship('Match', backref='stage', lazy='dynamic')

    def __init__(self, event, start_date, end_date):
        self.event = event
        self.start_date = start_date
        self.end_date = end_date


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(254), unique=True)
    password_hash = db.Column(db.String(64))
    admin = db.Column(db.Boolean)
    join_date = db.Column(db.Date)

    created_leagues = db.relationship('League', backref='creator', lazy='dynamic')
    memberships = db.relationship('Membership', backref='user', lazy='dynamic')
    participants = db.relationship('Participant', backref='user', lazy='dynamic')
    posts = db.relationship('Post', backref='author', lazy='dynamic')

    def __init__(self, name, email, password):
        self.name = name
        self.email = email
        self.set_password(password)
        self.join_date = date.today()

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password)

    def is_admin(self):
        return self.admin

    def is_anonymous(self):
        return False

    def is_member(self, league):
        leagues = [membership.league for membership in self.memberships]
        return league in leagues

    def get_auth_token(self):
        data = [str(self.id), self.password_hash.decode('utf-8')]
        return login_serializer.dumps(data)

    def get_leagues(self):
        return [membership.league for membership in self.memberships]

    def get_matches(self):
        matches = []
        for p in self.participants:
            matches.extend(p.get_matches())
        return matches

    def get_matches_count(self):
        num_matches = 0
        for p in self.participants:
            num_matches += p.get_matches_count()
        return num_matches

    def get_matches_won(self):
        matches_won = []
        for p in self.participants:
            matches_won.extend(p.get_matches_won())
        return matches_won

    def get_matches_won_count(self):
        num_matches_won = 0
        for p in self.participants:
            num_matches_won += p.get_matches_won_count()
        return num_matches_won

    def match_win_percentage(self):
        return self.get_matches_won_count() / self.get_matches_count()

    def __repr__(self):
        return '<{0}: {1}, {2}>'.format(self.__class__.__name__, self.name, self.email)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name


class AnonymousUser(AnonymousUserMixin):

    def is_admin(self):
        return False

    def is_anonymous(self):
        return True

    def is_member(self, league):
        return False


@login_manager.user_loader
def load_user(userid):
    return User.query.filter_by(id=userid).first()


@login_manager.token_loader
def load_token(token):
    data = login_serializer.loads(token)
    user = User.query.filter_by(id=data[0]).first()
    if user and data[1] == user.password_hash:
        return user
    return None


login_manager.anonymous_user = AnonymousUser
