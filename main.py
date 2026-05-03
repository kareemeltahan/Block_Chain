"""
main.py
───────
End-to-end demo. Exercises every feature in correct dependency order.

Run:
    python main.py

On first run: deploys all 7 contracts, binds sub-contracts, grants roles.
Subsequent runs reuse deployed addresses from config.json.
"""
from python.datasource.university_ds import UniversityDataSource

ds = UniversityDataSource()


def hr(title: str) -> None:
    print(f"\n{'═' * 62}")
    print(f"  {title}")
    print('═' * 62)


def print_transcript(student_id: int) -> None:
    student    = ds.get_student(student_id)
    major      = ds.get_major(student.major_id)
    transcript = ds.get_full_transcript(student_id)
    print(f"\n  ── {student.name}  [{major.code}]  (ID {student_id}) ──")
    if not transcript:
        print("     (no enrollments)")
        return
    for sem in transcript:
        gpa_str = f"{sem.gpa:.2f}/4.00" if sem.gpa is not None else "ungraded"
        print(f"  [{sem.semester}]  courses={sem.total_courses}  graded={sem.graded_count}  GPA={gpa_str}")
        for e in sem.enrollments:
            if e.mark > 0:
                mark_str = f"{e.mark:>3}/100  {e.grade:<3}  {e.gpa_points:.1f}/4.0"
            else:
                mark_str = "  —/100  —    —/4.0"
            flag = "" if e.active else " (dropped)"
            print(f"    {e.course_id:<12}  {mark_str}{flag}")


if __name__ == "__main__":

    from python.blockchain.provider import get as get_w3
    w3       = get_w3()
    accounts = w3.eth.accounts   # Anvil pre-funded accounts

    # ─────────────────────────────────────────────────────────────────────────
    hr("1 · Majors")
    ds.add_major("CS",  "Computer Science",       "Software, systems, algorithms")
    ds.add_major("AI",  "Artificial Intelligence","ML, NLP, computer vision")
    ds.add_major("IT",  "Information Technology", "Networks, sysadmin, security")
    ds.add_major("CYB", "Cybersecurity",           "Offensive and defensive security")
    ds.add_major("EE",  "Electrical Engineering",  "Circuits, signals, embedded systems")

    for m in ds.get_all_majors():
        print(f"  [{m.id}] {m.code:<5} — {m.name}")

    # ─────────────────────────────────────────────────────────────────────────
    hr("2 · Professors  (each needs a distinct address — not the deployer's)")
    # Anvil account[0] is the deployer. Use accounts[1..3] for professors.
    prof_addrs = accounts[1], accounts[2], accounts[3]

    ds.add_professor("Dr. Smith",   "Computer Science", prof_addrs[0])
    ds.add_professor("Dr. Johnson", "Mathematics",      prof_addrs[1])
    ds.add_professor("Dr. Chen",    "Cybersecurity",    prof_addrs[2])

    for p in ds.get_all_professors():
        print(f"  [{p.id}] {p.name:<22} dept={p.department:<22} addr={p.professor_address[:14]}…")

    # ─────────────────────────────────────────────────────────────────────────
    hr("3 · Students")
    ds.add_student("Alice",  major_id=1, year=2024, professor_id=1)
    ds.add_student("Bob",    major_id=2, year=2024, professor_id=2)
    ds.add_student("Carol",  major_id=3, year=2023, professor_id=1)
    ds.add_student("Dave",   major_id=4, year=2025, professor_id=3)
    ds.add_student("Eve",    major_id=1, year=2025, professor_id=2)

    for s in ds.get_all_students():
        major = ds.get_major(s.major_id)
        print(f"  [{s.id}] {s.name:<10} major={major.code:<5} year={s.year}  supervisor={s.academic_supervisor[:14]}…")

    # ─────────────────────────────────────────────────────────────────────────
    hr("4 · Courses")
    ds.create_course("CS101",   "Intro to Programming",   professor_id=1)
    ds.create_course("CS201",   "Data Structures",        professor_id=1)
    ds.create_course("AI301",   "Machine Learning",       professor_id=2)
    ds.create_course("MATH101", "Discrete Mathematics",   professor_id=2)
    ds.create_course("CYB401",  "Network Security",       professor_id=3)

    for c in ds.get_all_courses():
        p = ds.get_professor(c.professor_id)
        print(f"  {c.id:<10}  {c.name:<30}  ({p.name})")

    # ─────────────────────────────────────────────────────────────────────────
    hr("5 · Enrollment — spring2025")
    SEM_A = "spring2025"
    ds.enroll(SEM_A, student_id=1, course_id="CS101")
    ds.enroll(SEM_A, student_id=1, course_id="MATH101")
    ds.enroll(SEM_A, student_id=2, course_id="AI301")
    ds.enroll(SEM_A, student_id=2, course_id="MATH101")
    ds.batch_enroll(SEM_A, student_ids=[3, 4, 5], course_id="CS101")
    print(f"  Enrolled spring2025. Course CS101 roster:")
    for e in ds.get_course_enrollments("CS101"):
        if e.active:
            s = ds.get_student(e.student_id)
            print(f"    student {e.student_id} — {s.name}")

    # ─────────────────────────────────────────────────────────────────────────
    hr("6 · Marks — spring2025")
    ds.update_mark(SEM_A, student_id=1, course_id="CS101",   mark=88)
    ds.update_mark(SEM_A, student_id=1, course_id="MATH101", mark=74)
    ds.update_mark(SEM_A, student_id=2, course_id="AI301",   mark=91)
    ds.update_mark(SEM_A, student_id=2, course_id="MATH101", mark=83)
    ds.update_mark(SEM_A, student_id=3, course_id="CS101",   mark=67)
    ds.update_mark(SEM_A, student_id=4, course_id="CS101",   mark=79)
    ds.update_mark(SEM_A, student_id=5, course_id="CS101",   mark=95)
    print("  Marks recorded for spring2025.")

    # ─────────────────────────────────────────────────────────────────────────
    hr("7 · Enrollment — autumn2025  (second semester)")
    SEM_B = "autumn2025"
    ds.enroll(SEM_B, student_id=1, course_id="CS201")
    ds.enroll(SEM_B, student_id=1, course_id="AI301")
    ds.enroll(SEM_B, student_id=2, course_id="CS201")
    ds.enroll(SEM_B, student_id=3, course_id="CYB401")
    ds.enroll(SEM_B, student_id=5, course_id="CS201")
    ds.enroll(SEM_B, student_id=5, course_id="CYB401")
    ds.update_mark(SEM_B, student_id=1, course_id="CS201",  mark=92)
    ds.update_mark(SEM_B, student_id=1, course_id="AI301",  mark=85)
    ds.update_mark(SEM_B, student_id=2, course_id="CS201",  mark=77)
    ds.update_mark(SEM_B, student_id=3, course_id="CYB401", mark=95)
    ds.update_mark(SEM_B, student_id=5, course_id="CS201",  mark=89)
    ds.update_mark(SEM_B, student_id=5, course_id="CYB401", mark=93)
    print("  autumn2025 enrollments and marks recorded.")

    # ─────────────────────────────────────────────────────────────────────────
    hr("8 · Transcripts")
    for sid in [1, 2, 3, 5]:
        print_transcript(sid)

    # ─────────────────────────────────────────────────────────────────────────
    hr("9 · GPA overview  (4.0 scale)")
    for sid in [1, 2, 3, 4, 5]:
        try:
            s   = ds.get_student(sid)
            gpa = ds.get_gpa(sid)
            gpa_str = f"{gpa:.2f}/4.00" if gpa is not None else "no grades yet"
            print(f"  {s.name:<10}  cumulative GPA = {gpa_str}")
        except Exception as exc:
            print(f"  student {sid}: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    hr("10 · RBAC — grant registrar to accounts[4]")
    reg_addr = accounts[4]
    ds.grant_role("REGISTRAR_ROLE", reg_addr)
    roles = ds.get_all_roles()
    print(f"  ADMIN_ROLE:      {roles['ADMIN_ROLE']}")
    print(f"  REGISTRAR_ROLE:  {roles['REGISTRAR_ROLE']}")
    print(f"  INSTRUCTOR_ROLE: {[a[:14]+'…' for a in roles['INSTRUCTOR_ROLE']]}")

    # ─────────────────────────────────────────────────────────────────────────
    hr("11 · Unenroll — Alice drops MATH101 from spring2025")
    ds.unenroll(SEM_A, student_id=1, course_id="MATH101")
    print("  Alice's spring2025 after drop:")
    for e in ds.get_semester_enrollments(1, SEM_A):
        status = "active" if e.active else "dropped"
        print(f"    {e.course_id}  mark={e.mark}  ({status})")

    # ─────────────────────────────────────────────────────────────────────────
    hr("12 · Cascade delete — delete Dr. Johnson (removes AI301, MATH101)")
    before = [c.id for c in ds.get_all_courses()]
    print(f"  Courses before: {before}")
    ds.delete_professor(professor_id=2)
    after = [c.id for c in ds.get_all_courses()]
    print(f"  Courses after:  {after}")
    print(f"  INSTRUCTOR_ROLE after: {[a[:14]+'…' for a in ds.get_all_roles()['INSTRUCTOR_ROLE']]}")

    # ─────────────────────────────────────────────────────────────────────────
    hr("13 · Retake — Alice re-enrolls in CS101 spring2026")
    SEM_C = "spring2026"
    ds.enroll(SEM_C, student_id=1, course_id="CS101")
    ds.update_mark(SEM_C, student_id=1, course_id="CS101", mark=97)
    print_transcript(1)

    # ─────────────────────────────────────────────────────────────────────────
    hr("14 · Full system status")
    print(f"\n  Professors: {len(ds.get_all_professors())}")
    print(f"  Students:   {len(ds.get_all_students())}")
    print(f"  Courses:    {len(ds.get_all_courses())}")
    print(f"  Majors:     {len(ds.get_all_majors())}")

    print("\n  ✓ Demo complete.")
