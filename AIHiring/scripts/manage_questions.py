#!/usr/bin/env python3
"""Simple management script for `data/questions/interview_questions.json`.

Usage examples:
  - List roles: python3 scripts/manage_questions.py list-roles
  - List questions for a role: python3 scripts/manage_questions.py list --role software_engineer
  - Add question: python3 scripts/manage_questions.py add --role software_engineer --question "What is X?" --type technical --difficulty medium
"""
import argparse
import json
from pathlib import Path

QUESTIONS_FILE = Path('data/questions/interview_questions.json')


def load_questions():
    if not QUESTIONS_FILE.exists():
        print(f"Questions file not found: {QUESTIONS_FILE}")
        return {}
    return json.loads(QUESTIONS_FILE.read_text(encoding='utf-8'))


def save_questions(data):
    QUESTIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def list_roles():
    data = load_questions()
    if not data:
        return
    for role in sorted(data.keys()):
        print(role)


def list_questions(role):
    data = load_questions()
    role_data = data.get(role)
    if not role_data:
        print(f"No questions found for role: {role}")
        return
    for i, q in enumerate(role_data, start=1):
        q_text = q.get('question') or q.get('text')
        print(f"{i}. {q_text} ({q.get('type','?')}, {q.get('difficulty','?')})")


def add_question(role, question, qtype='technical', difficulty='medium'):
    data = load_questions()
    if role not in data:
        data[role] = []
    new_q = {
        'question': question.strip(),
        'type': qtype,
        'difficulty': difficulty
    }
    data[role].append(new_q)
    save_questions(data)
    print(f"Added question to role '{role}': {question}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')

    sub.add_parser('list-roles')

    list_parser = sub.add_parser('list')
    list_parser.add_argument('--role', required=True)

    add_parser = sub.add_parser('add')
    add_parser.add_argument('--role', required=True)
    add_parser.add_argument('--question', required=True)
    add_parser.add_argument('--type', default='technical')
    add_parser.add_argument('--difficulty', default='medium')

    args = parser.parse_args()

    if args.cmd == 'list-roles':
        list_roles()
    elif args.cmd == 'list':
        list_questions(args.role)
    elif args.cmd == 'add':
        add_question(args.role, args.question, args.type, args.difficulty)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
