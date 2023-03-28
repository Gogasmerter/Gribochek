import datetime
from copy import copy

from flask import Flask, redirect, render_template, request, abort, session
from PIL import Image
from flask_login import LoginManager, current_user, login_required, logout_user, login_user
from json import dumps, loads

from data import db_session
from data.audiences import Audience
from data.days import Day
from data.groups import Group
from data.users import User
from data.weeks import Week
from data.working_days import WorkingDays
from forms.admin import RegisterAdminForm
from forms.audience import AudienceForm
from forms.edit_audience import EditAudienceForm
from forms.edit_user import EditUserForm
from forms.group import CreateGroupForm
from forms.user import RegisterForm
from static.python.functions import create_main_admin, DateEncoder, DecodeDate, get_pars_list, get_need_days, \
    load_week_by_group_form, get_week_audience, get_teacher_par_list
from static.python.vClassFunctions import get_day
from static.python.variables import ST_message, DAYS, PARS_TIMES

current_user.is_authenticated: bool

app = Flask(__name__)
app.config['SECRET_KEY'] = 'very_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)


@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get('message'):
        session['message'] = dumps(ST_message)
    session['form_group'] = None
    db_sess = db_session.create_session()
    smessage = session['message']
    audiences = db_sess.query(Audience).all()
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    weeks = list(map(lambda au: get_week_audience(db_sess, au.id, datetime.date.today()), audiences))
    if request.method == 'POST':
        password = request.form['password']
        email = request.form['email']
        remember = bool(request.form.getlist('remember'))
        print(remember)
        user = db_sess.query(User).filter(User.email == email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            return redirect('/')
        message = {'status': 0, 'text': 'Неверный логин или пароль'}
        return render_template('index.html',
                               title='Главная страница', message=dumps(message), len=len,
                               weeks=weeks, dicts=dicts)
    session['message'] = dumps(ST_message)
    print(weeks)
    return render_template('index.html', title='Главная страница', message=smessage, len=len,
                           weeks=weeks, dicts=dicts)


@app.route('/time_table')
def to_time_table():
    date = datetime.date.today()
    return redirect(f'/time_table/{DateEncoder(date)}')


@app.route('/time_table/<date1>')
def time_table(date1):
    print(date1)
    try:
        date = DecodeDate(date1)
    except Exception:
        abort(404)
    st_date = date - datetime.timedelta(days=date.weekday())
    session['form_group'] = None
    db_sess = db_session.create_session()
    smessage = session['message']
    dates = {'st_date': st_date, 'en_date': st_date + datetime.timedelta(days=6),
             'back_week': DateEncoder(st_date - datetime.timedelta(days=7)),
             'next_week': DateEncoder(st_date + datetime.timedelta(days=7))}
    audiences = db_sess.query(Audience).all()
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    weeks = list(map(lambda au: get_week_audience(db_sess, au.id, date), audiences))
    if request.method == 'POST':
        password = request.form['password']
        email = request.form['email']
        remember = bool(request.form.getlist('remember'))
        print(remember)
        user = db_sess.query(User).filter(User.email == email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            return redirect(f'/time_table/{date1}')
        message = {'status': 0, 'text': 'Неверный логин или пароль'}
        return render_template('time_table.html',
                               title='Расписание', message=dumps(message), len=len,
                               weeks=weeks, dicts=dicts, st_date=st_date)

    session['message'] = dumps(ST_message)
    return render_template('time_table.html', title='Расписание', message=smessage, len=len,
                           weeks=weeks, dicts=dicts, dates=dates)


@app.route('/profile/<int:user_id>', methods=["GET", "POST"])
def profile(user_id):
    db_sess = db_session.create_session()
    db_sess.query(User).get(user_id)
    user = db_sess.query(User).filter(User.id == user_id).first()
    if not user:
        abort(404)
    if user.role == 4:
        abort(404)
    if user.role == 3 and current_user.role != 4:
        abort(404)
    if current_user.role == 1 and current_user.id != user_id:
        abort(404)
    smessage = session['message']
    session['message'] = dumps(ST_message)
    return render_template('profile.html', title='Профиль', message=smessage, user=user)


@app.route('/register/admin', methods=['GET', 'POST'])
def register_admin():
    if not current_user.is_authenticated:
        abort(404)
    if not current_user.role == 4:
        abort(404)
    form = RegisterAdminForm()
    db_sess = db_session.create_session()
    users = db_sess.query(User).all()
    last_id = users[-1].id + 1

    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            message = {'status': 0, 'text': 'Пароли не совпадают'}
            return render_template('register_admin.html', title='Регистрация админа',
                                   form=form,
                                   message=dumps(message))
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            message = {'status': 0, 'text': 'Такой пользователь уже есть'}
            return render_template('register_admin.html', title='Регистрация админа',
                                   form=form,
                                   message=dumps(message))
        user = User(
            id=last_id,
            email=form.email.data,
            role=3,
            img=f'img/users/{last_id}.jpg',
        )
        Image.open(
            'static/img/admin.jpg').save(f'static/img/users/{last_id}.jpg')
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        message = dumps({'status': 1, 'text': 'Администратор зарегистрирован'})
        session['message'] = message
        return redirect('/show/admins')
    return render_template('register_admin.html', title='Регистрация админа', form=form, message=dumps(ST_message))


@app.route('/register/teacher', methods=['GET', 'POST'])
def register_teacher():
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    form = RegisterForm()
    db_sess = db_session.create_session()
    users = db_sess.query(User).all()
    last_id = users[-1].id + 1

    if form.validate_on_submit():
        print(0)
        if form.password.data != form.password_again.data:
            message = {'status': 0, 'text': 'Пароли не совпадают'}
            return render_template('register_teacher.html', title='Регистрация преподавателя',
                                   form=form,
                                   message=dumps(message))
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            message = {'status': 0, 'text': 'Такой пользователь уже есть'}
            return render_template('register_teacher.html', title='Регистрация преподавателя',
                                   form=form,
                                   message=dumps(message))
        user = User(
            id=last_id,
            name=form.name.data,
            surname=form.surname.data,
            otchestvo=form.otchestvo.data,
            email=form.email.data,
            role=2,
        )
        print(1)
        if form.img.data:
            form.img.data.save(f"static/img/users/{last_id}.jpg")
        else:
            Image.open(
                f'static/img/teachers/no-img.jpg').save(f"static/img/users/{last_id}.jpg")
        user.img = f'img/users/{last_id}.jpg'
        user.set_password(form.password.data)
        db_sess.add(user)
        wdays = WorkingDays(
            teacher_id=last_id,
            days='1✡1✡1✡1✡1✡1',
        )
        db_sess.add(wdays)
        db_sess.commit()
        message = dumps({'status': 1, 'text': 'Учитель зарегистрирован'})
        session['message'] = message
        return redirect('/show/teachers')
    return render_template('register_teacher.html', title='Регистрация преподавателя', form=form, message=dumps(ST_message))


@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    form = RegisterForm()
    db_sess = db_session.create_session()
    users = db_sess.query(User).all()
    last_id = 1 if not users else users[-1].id + 1
    smessage = session['message']

    if request.method == 'GET':
        pass
        # groups = db_sess.query(Group.name).all()
        # groups = [(1, 'Первая группа'), (2, 'Вторая группа')]
        # form.group.choices = groups

    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            message = {'status': 0, 'text': 'Пароли не совпадают'}
            return render_template('register_student.html', title='Регистрация студента',
                                   form=form,
                                   message=dumps(message))
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            message = {'status': 0, 'text': 'Такой пользователь уже есть'}
            return render_template('register_student.html', title='Регистрация студента',
                                   form=form,
                                   message=dumps(message))
        user = User(
            id=last_id,
            name=form.name.data,
            surname=form.surname.data,
            otchestvo=form.otchestvo.data,
            email=form.email.data,
            role=1,
        )
        if form.img.data:
            img1 = form.img.data
            img1.save(f"static/img/users/{last_id}.jpg")
        else:
            Image.open(
                f'static/img/users/no-img.jpg').save(f"static/img/users/{last_id}.jpg")
        user.img = f'img/users/{last_id}.jpg'
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        message = dumps({'status': 1, 'text': 'Ученик зарегистрирован'})
        session['message'] = message
        return redirect('/show/users')
    session['message'] = dumps(ST_message)
    return render_template('register_student.html', title='Регистрация студента', form=form, message=smessage)


@app.route('/create_audience', methods=['GET', 'POST'])
def create_audience():
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    form = AudienceForm()
    smessage = session['message']
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        if db_sess.query(Audience).filter(Audience.name == form.name.data).first():
            message = {'status': 0, 'text': 'Такая аудитория уже есть'}
            return render_template('create_audience.html', title='Создание аудитории',
                                   form=form,
                                   message=dumps(message))
        audiences = db_sess.query(Audience).all()
        last_id = audiences[-1].id + 1 if audiences else 0
        audience = Audience(
            id=last_id,
            name=form.name.data
        )
        if form.is_eventable.data:
            audience.is_eventable = form.is_eventable.data
        if form.img.data:
            form.img.data.save(f'static/img/audiences/au{last_id}im.jpg')
        else:
            Image.open('static/img/standarts/audience.jpg').save(f'static/img/audiences/au{last_id}im.jpg')
        audience.image = f'img/audiences/au{last_id}im.jpg'

        db_sess.add(audience)
        db_sess.commit()
        message = dumps({'status': 1, 'text': 'Аудитория создана'})
        session['message'] = message
        return redirect(f'/audience_profile/{last_id}')
    session['message'] = dumps(ST_message)
    return render_template('create_audience.html', title='Создание аудитории', form=form,
                           message=smessage)


@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role in (1, 2) and current_user.id != user_id:
        abort(404)
    db_sess = db_session.create_session()
    user = db_sess.query(User).get(user_id)
    if not user:
        abort(404)
    if user.role == 4:
        abort(404)
    if current_user.role == user.role and current_user.id != user.id:
        abort(404)
    form = EditUserForm()
    smessage = session['message']
    if request.method == 'GET':
        if current_user.id == user.id or user.role == 3:
            form.email.data = user.email
        else:
            form.name.data = user.name
            form.surname.data = user.surname
            form.otchestvo.data = user.otchestvo
    if form.validate_on_submit():
        if form.new_password.data != form.password_again.data:
            message = {'status': 0, 'text': 'Пароли не совпадают'}
            return render_template('edit_user.html', title='Изменение профиля',
                                   form=form, user=user,
                                   message=dumps(message))
        if current_user.id == user.id:
            if db_sess.query(User).filter(User.email == form.email.data).first() and form.email.data != user.email:
                message = {'status': 0, 'text': 'Такой пользователь уже есть'}
                return render_template('edit_user.html', title='Изменение профиля', user=user,
                                       form=form, message=dumps(message))
            if not user.check_password(form.password.data):
                message = {'status': 0, 'text': 'Введён неверный старый пароль'}
                return render_template('edit_user.html', title='Изменение профиля',
                                       form=form, user=user,
                                       message=dumps(message))
            user.email = form.email.data
            if form.img.data:
                form.img.data.save(f'static/img/users/{user.id}.jpg')
            if form.new_password.data:
                user.set_password(form.new_password.data)
            db_sess.merge(user)
            db_sess.commit()
            message = dumps({'status': 1, 'text': 'Профиль изменён'})
            session['message'] = message
            return redirect(f'/profile/{user_id}')
        else:
            if user.role == 3:
                if db_sess.query(User).filter(User.email == form.email.data).first() and form.email.data != user.email:
                    message = {'status': 0, 'text': 'Такой пользователь уже есть'}
                    return render_template('edit_user.html', title='Изменение профиля', user=user,
                                           form=form, message=dumps(message))
                user.email = form.email.data
                if form.new_password.data:
                    user.set_password(form.new_password.data)
                db_sess.merge(user)
                db_sess.commit()
                message = dumps({'status': 1, 'text': 'Профиль изменён'})
                session['message'] = message
                return redirect(f'/profile/{user_id}')
            else:
                if form.new_password.data:
                    user.set_password(form.new_password.data)
                user.name = form.name.data
                user.surname = form.surname.data
                user.otchestvo = form.otchestvo.data
                db_sess.merge(user)
                db_sess.commit()
                message = dumps({'status': 1, 'text': 'Профиль изменён'})
                session['message'] = message
                return redirect(f'/profile/{user_id}')
    session['message'] = dumps(ST_message)
    return render_template('edit_user.html', title='Изменение профиля', form=form, message=smessage,
                           user=user)


@app.route('/edit_audience/<int:aud_id>', methods=['GET', 'POST'])
def edit_audience(aud_id):
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    form = EditAudienceForm()
    smessage = session['message']
    db_sess = db_session.create_session()
    audience = db_sess.query(Audience).filter(Audience.id == aud_id).first()
    if request.method == 'GET':
        form.name.data = audience.name
        form.is_eventable.data = audience.is_eventable
    if form.validate_on_submit():
        if db_sess.query(Audience).filter(Audience.name == form.name.data).first() and \
                audience.name != form.name.data:
            message = {'status': 0, 'text': 'Такая аудитория уже есть'}
            return render_template('edit_audience.html', title='Изменение аудитории',
                                   form=form,
                                   message=dumps(message))
        if form.name.data:
            audience.name = form.name.data
        audience.is_eventable = form.is_eventable.data
        if form.img.data:
            form.img.data.save(f'static/{audience.image}')
        db_sess.merge(audience)
        db_sess.commit()
        message = dumps({'status': 1, 'text': 'Аудитория изменена'})
        session['message'] = message
        return redirect('/show/audiences')
    session['message'] = dumps(ST_message)
    return render_template('edit_audience.html', title='Изменение аудитории', form=form,
                           message=smessage)


@app.route('/edit_week/<int:week_id>')
def edit_week(week_id):
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    smessage = session['message']

    db_sess = db_session.create_session()
    week1 = db_sess.query(Week).get(week_id)
    if not week1:
        abort(404)

    audience = db_sess.query(Audience).get(week1.audience_id)
    week = get_week_audience(db_sess, audience.id, week1.week_start_date)
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    session['message'] = dumps(ST_message)
    return render_template('edit_week.html', title='Редиктирование недели', message=smessage,
                           week=week, dicts=dicts, audience=audience)


@app.route('/edit_day/<int:audience_id>/<int:day_id>')
def edit_day(audience_id, day_id):
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    smessage = session['message']

    db_sess = db_session.create_session()
    day1 = db_sess.query(Day).get(day_id)
    if not day1:
        abort(404)

    audience = db_sess.query(Audience).get(audience_id)
    if not audience:
        abort(404)
    week = db_sess.query(Week).filter(Week.week_start_date <= day1.date,
                                      day1.date <= Week.week_end_date,
                                      Week.audience_id == audience_id).first()
    if not week:
        abort(404)
    day = get_day(day_id, db_sess)
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    session['message'] = dumps(ST_message)
    return render_template('edit_day.html', title='Редиктирование дня', message=smessage,
                           dicts=dicts, day=day, day1=day1, audience=audience, week=week)


@app.route('/add_par/<int:audience_id>/<int:day_id>/<int:par_index>', methods=['GET', 'POST'])
def delete_par(audience_id, day_id, par_index):
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    smessage = session['message']

    db_sess = db_session.create_session()
    day1 = db_sess.query(Day).get(day_id)
    if not day1:
        abort(404)

    audience = db_sess.query(Audience).get(audience_id)
    day = get_day(day_id, db_sess)
    group = day.pars[par_index]
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    if request.method == 'POST':
        if par_index == 0:
            day1.p1group = None
        if par_index == 1:
            day1.p2group = None
        if par_index == 2:
            day1.p3group = None
        if par_index == 3:
            day1.p4group = None
        if par_index == 4:
            day1.p5group = None
        if par_index == 5:
            day1.p6group = None
        db_sess.commit()
        return redirect(f'/edit_day/{audience_id}/{day.id}')

    session['message'] = dumps(ST_message)
    return render_template('delete_par.html', title='Удаление пары', message=smessage, par_index=par_index,
                           dicts=dicts, day=day, day1=day1, audience=audience, par=group)


@app.route('/delete_par/<int:audience_id>/<int:day_id>/<int:par_index>', methods=['GET', 'POST'])
def delete_par(audience_id, day_id, par_index):
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    smessage = session['message']

    db_sess = db_session.create_session()
    day1 = db_sess.query(Day).get(day_id)
    if not day1:
        abort(404)

    audience = db_sess.query(Audience).get(audience_id)
    day = get_day(day_id, db_sess)
    group = day.pars[par_index]
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    if request.method == 'POST':
        if par_index == 0:
            day1.p1group = None
        if par_index == 1:
            day1.p2group = None
        if par_index == 2:
            day1.p3group = None
        if par_index == 3:
            day1.p4group = None
        if par_index == 4:
            day1.p5group = None
        if par_index == 5:
            day1.p6group = None
        db_sess.commit()
        return redirect(f'/edit_day/{audience_id}/{day.id}')

    session['message'] = dumps(ST_message)
    return render_template('delete_par.html', title='Удаление пары', message=smessage, par_index=par_index,
                           dicts=dicts, day=day, day1=day1, audience=audience, par=group)


@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role not in (3, 4):
        abort(404)
    form = CreateGroupForm()
    session['form_group'] = None
    smessage = session['message']
    db_sess = db_session.create_session()
    if not form.teacher_id.choices:
        teachers_list = list(map(lambda u: (u.id, f'{u.surname} {u.name[0]}.' + (f' {u.otchestvo[0]}.' if u.otchestvo else '')),
                                 db_sess.query(User).filter(User.role == 2).all()))
        form.teacher_id.choices = teachers_list
    if not form.audience_id.choices:
        audience_list = list(map(lambda au: (au.id, au.name),
                             db_sess.query(Audience).filter(Audience.is_eventable == False).all()))
        form.audience_id.choices = audience_list

    if request.method == 'GET':
        pass
    if form.validate_on_submit():
        teacher_id = int(form.teacher_id.data)
        audience_id = int(form.audience_id.data)
        st_date = form.course_start_date.data
        en_date = form.course_end_date.data
        day0 = form.day0.data
        day1 = form.day1.data
        day2 = form.day2.data
        day3 = form.day3.data
        day4 = form.day4.data
        day5 = form.day5.data
        if (en_date - st_date).days < 14:
            message = dumps({'status': 0, 'text': 'Курс должен идти больше 2-х недель'})
            return render_template('create_group.html', title='Создание группы', form=form,
                                   message=message)
        if day0 + day1 + day2 + day3 + day4 + day5 != 2:
            message = dumps({'status': 0, 'text': 'Суммарное количество пар на группу должно быть 2'})
            return render_template('create_group.html', title='Создание группы', form=form,
                                   message=message)
        wdays = db_sess.query(WorkingDays).get(teacher_id)
        wdays = wdays.days.split('✡')
        days = list(map(bool, [day0, day1, day2, day3, day4, day5]))
        for i in range(6):
            if int(wdays[i]) < int(days[i]):
                message = dumps({'status': 0, 'text': f'Учитель не работает в день {DAYS[i + 1]}'})
                return render_template('create_group.html', title='Создание группы', form=form,
                                       message=message)
        form_group = {
            'subject': form.subject.data,
            'teacher_id': teacher_id,
            'audience_id': audience_id,
            'st_date': DateEncoder(st_date),
            'en_date': DateEncoder(en_date),
            'day0': bool(day0),
            'day1': bool(day1),
            'day2': bool(day2),
            'day3': bool(day3),
            'day4': bool(day4),
            'day5': bool(day5),
            'day0time': '',
            'day1time': '',
        }
        print(form_group)
        need = get_need_days(form_group)
        t_par = get_teacher_par_list(db_sess=db_session.create_session(), form=form_group)
        a_par = get_pars_list(db_session.create_session(), form=form_group, need_days=need)
        a_par = list(filter(lambda x: x, a_par))
        if len(a_par) == 1:
            a_par = [a_par[0], a_par[0]]
        arr = []
        for dd1, dd2 in zip(t_par, a_par):
            arr1 = []
            for pa1, pa2 in zip(dd1, dd2):
                if not pa1 or not pa2:
                    arr1.append(None)
                else:
                    arr1.append(pa1)
            arr.append(arr1)
        print(arr)
        for day in arr:
            if not day:
                continue
            if not any(day):
                session['message'] = dumps({'status': 0, 'text': 'Рассписание составить невозможно'})
                return redirect('/create_group')
            if need[0] == need[1] and len(list(filter(lambda p: p, day))) < 2:
                session['message'] = dumps({'status': 0, 'text': 'Рассписание составить невозможно'})
                return redirect('/create_group')
        form_group['timesd'] = arr

        session['form_group'] = dumps(form_group)
        # frm = loads(session['form_group'])
        # frm['st_date'] = DecodeDate(frm['st_date'])
        # frm['en_date'] = DecodeDate(frm['en_date'])
        return redirect('/choice_group_days')

    session['message'] = dumps(ST_message)
    return render_template('create_group.html', title='Создание группы', form=form,
                           message=smessage)


@app.route('/choice_group_days', methods=['GET', 'POST'])
def choice_group_days():
    if not session['form_group']:
        abort(404)
    form = loads(session['form_group'])
    form['st_date'] = DecodeDate(form['st_date'])
    form['en_date'] = DecodeDate(form['en_date'])
    smessage = session['message']
    need_days = get_need_days(form=form)
    days = form['timesd']
    print(days)
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    lef_days = 1 if need_days[0] == need_days[1] else 2
    # if request.method == 'GET':
    #     for day in days:
    #         if not day:
    #             continue
    #         if not any(day):
    #             session['message'] = dumps({'status': 0, 'text': 'Рассписание составить невозможно'})
    #             return redirect('/create_group')
    #         if lef_days == 1 and len(list(filter(lambda p: p, day))) < 2:
    #             session['message'] = dumps({'status': 0, 'text': 'Рассписание составить невозможно'})
    #             return redirect('/create_group')
    if request.method == 'POST':
        remember1 = request.form.getlist(f'remember0')
        remember2 = request.form.getlist(f'remember1')
        if not remember1 or not remember2:
            message = dumps({'status': 0, 'text': 'Выберите 2 промежутка времени'})
            return render_template('choice_group_days.html', title='Выбор расписания', message=message,
                                   days=days, form=form, dicts=dicts, need_days=need_days, lef_days=lef_days)
        remember1 = int(remember1[0])
        remember2 = int(remember2[0])
        if remember1 == remember2 and lef_days == 1:
            message = dumps({'status': 0, 'text': 'Выберите разное время'})
            return render_template('choice_group_days.html', title='Выбор расписания', message=message,
                                   days=days, form=form, dicts=dicts, need_days=need_days, lef_days=lef_days)
        form['st_date'] = DateEncoder(form['st_date'])
        form['en_date'] = DateEncoder(form['en_date'])
        form['day0time'] = remember1
        form['day1time'] = remember2
        form['days'] = need_days

        session['form_group'] = dumps(form)
        return redirect('/accept_create_group')
    session['message'] = dumps(ST_message)
    return render_template('choice_group_days.html', title='Выбор расписания', message=smessage,
                           days=days, form=form, dicts=dicts, need_days=need_days, lef_days=lef_days)


@app.route('/accept_create_group', methods=['GET', 'POST'])
def accept_create_group():
    if not session['form_group']:
        abort(404)
    form = loads(session['form_group'])
    form['st_date'] = DecodeDate(form['st_date'])
    form['en_date'] = DecodeDate(form['en_date'])
    if 'day0time' not in form.keys():
        abort(404)
    smessage = session['message']
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    db_sess = db_session.create_session()
    groups = db_sess.query(Group).all()
    last_id = 1 if not groups else groups[-1].id + 1
    teacher = db_sess.query(User).get(form['teacher_id'])
    audience = db_sess.query(Audience).get(form['audience_id'])
    if request.method == 'POST':
        l = load_week_by_group_form(db_sess, form)
        if l:
            session['message'] = dumps({'status': 1, 'text': 'Группа создана'})
            return redirect('/show/groups')
    print(form)
    session['message'] = dumps(ST_message)
    return render_template('accept_create_group.html', title='Подтверждение создания', message=smessage,
                           form=form, last_id=last_id, teacher=teacher, audience=audience, dicts=dicts)


@app.route('/show/users')
def show_users():
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role == 1:
        abort(404)
    smessage = session['message']
    db_sess = db_session.create_session()
    users = db_sess.query(User).filter(User.role == 1).all()

    session['message'] = dumps(ST_message)
    return render_template('show_users.html', message=smessage, users=users)


@app.route('/show/teachers')
def show_teachers():
    if not current_user.is_authenticated:
        abort(404)
    smessage = session['message']
    db_sess = db_session.create_session()
    teachers = db_sess.query(User).filter(User.role == 2).all()
    session['message'] = dumps(ST_message)
    return render_template('show_teachers.html', message=smessage, teachers=teachers, title='Список учителей')


@app.route('/show/admins')
def show_admins():
    if not current_user.is_authenticated:
        abort(404)
    if current_user.role != 4:
        abort(404)
    smessage = session['message']
    db_sess = db_session.create_session()
    admins = db_sess.query(User).filter(User.role == 3).all()
    session['message'] = dumps(ST_message)
    return render_template('show_admins.html', message=smessage, admins=admins, title='Список администраторов')


@app.route('/show/audiences')
def show_audiences():
    if not current_user.is_authenticated:
        abort(404)
    smessage = session['message']
    db_sess = db_session.create_session()
    audiences = db_sess.query(Audience).all()

    session['message'] = dumps(ST_message)
    return render_template('show_audiences.html', audiences=audiences, title='Список аудиторий', message=smessage)


@app.route('/show/groups')
def show_groups():
    if not current_user.is_authenticated:
        abort(404)
    smessage = session['message']
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    db_sess = db_session.create_session()
    groups = db_sess.query(Group).all()
    audiences = []
    for i in range(len(groups)):
        audience = db_sess.query(Audience).filter(Audience.id == groups[i].audience_id).first()
        audiences.append(audience)
    session['message'] = dumps(ST_message)
    return render_template('show_groups.html', title='Список групп', message=smessage,
                           groups=groups, audiences=audiences, le=len(groups), dicts=dicts)


@app.route('/audience_profile/<int:aud_id>', methods=["GET", "POST"])
def audience_profile(aud_id):
    db_sess = db_session.create_session()
    db_sess.query(Audience).get(aud_id)
    audience = db_sess.query(Audience).filter(Audience.id == aud_id).first()
    smessage = session['message']
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    week = get_week_audience(db_sess, aud_id, datetime.date.today())
    session['message'] = dumps(ST_message)
    return render_template('audience_profile.html', title=f'{audience.name}', message=smessage, audience=audience,
                           week=week, dicts=dicts)


@app.route('/group_profile/<int:group_id>')
def group_profile(group_id):
    db_sess = db_session.create_session()
    group = db_sess.query(Group).get(group_id)
    if not group:
        abort(404)
    audience = db_sess.query(Audience).get(group.audience_id)
    dicts = {'DAYS': DAYS, 'PARS_TIMES': PARS_TIMES}
    week = get_week_audience(db_sess, audience.id, datetime.date.today())

    return render_template('group_profile.html', title='Страница группы', message=dumps(ST_message),
                           group=group, audience=audience, dicts=dicts, week=week)


@app.route('/user_delete/<int:user_id>', methods=['GET', 'POST'])
@login_required
def user_delete(user_id):
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == user_id,).first()
    if user:
        db_sess.delete(user)
        db_sess.commit()
    else:
        abort(404)
    return redirect('/')


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


if __name__ == '__main__':
    db_session.global_init("db/GriBD.db")
    create_main_admin(db_session.create_session())
    app.run(port=8080, host='127.0.0.1')
