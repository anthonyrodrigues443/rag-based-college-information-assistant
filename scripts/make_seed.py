"""Writes the demo college's document set into data/seed/."""
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "data" / "seed"
SEED.mkdir(parents=True, exist_ok=True)

DOCS = {
"sem-v-fee-extension": ("""---
title: Extension of last date for payment of Semester V tuition fee
date: 2026-08-14
kind: circular
source: Circulars, page 3
---

# Extension of last date for payment of Semester V tuition fee

The last date for payment of the Semester V tuition fee for all branches is extended to
29 August 2026. The earlier notified date was 22 August 2026. The extension applies to all
undergraduate branches and to both new and repeat registrations.

# Late fee

Payments made after 29 August 2026 attract a late fee of Rs. 500. The late fee is charged
per student and not per instalment. No further extension will be granted after this date.
Students who miss the extended date will not appear on the examination roll list until the
tuition fee and the late fee are both cleared.

# How to pay

Payment is accepted only through the student portal under Accounts, Pay Fees. Cash and
cheque payments are not accepted at the accounts counter. After payment the portal issues a
receipt within two working hours. Students must keep the receipt number for hostel and
examination form verification.

# Who to contact

Queries about failed transactions go to the Accounts Section, Room 104, Administrative
Building, between 10:00 and 16:00 on working days. A failed transaction where the amount was
debited is normally reversed by the bank within seven working days.
"""),

"kt-exam-form": ("""---
title: KT examination form submission window and late fee schedule
date: 2026-08-12
kind: circular
source: Circulars, page 3
---

# KT examination form submission window

The KT examination form for the odd semester 2026-27 can be submitted from 12 August 2026 to
26 August 2026 through the student portal. KT means a Keep Term backlog subject carried from
an earlier semester.

# Late fee schedule

Forms submitted from 27 August to 31 August 2026 attract a late fee of Rs. 300 per subject.
Forms submitted from 1 September to 4 September 2026 attract a late fee of Rs. 700 per
subject. No form is accepted after 4 September 2026 under any circumstances.

# Examination fee per subject

The KT examination fee is Rs. 400 per theory subject and Rs. 600 per laboratory subject.
A student may register a maximum of six KT subjects in one attempt.

# Required documents

The filled form must be uploaded with the fee receipt and the previous semester mark sheet.
Forms uploaded without a readable receipt are rejected and the student is informed on the
portal within two working days.
"""),

"revised-academic-calendar": ("""---
title: Revised academic calendar for the odd semester 2026-27
date: 2026-08-09
kind: circular
source: Circulars, page 4
---

# Revised academic calendar for the odd semester 2026-27

Teaching for the odd semester begins on 3 August 2026 and ends on 21 November 2026. The
revision shifts the internal assessment dates by one week from the calendar published in June.

# Internal assessment

The first internal assessment runs from 14 September to 19 September 2026. The second
internal assessment runs from 19 October to 24 October 2026. Practical and oral examinations
run from 24 November to 5 December 2026.

# End semester examination

The theory end semester examination begins on 8 December 2026. The detailed timetable is
published separately at least three weeks before the first paper.

# Holidays and breaks

The institute is closed from 18 October to 23 October 2026 for the festival break. The winter
break runs from 24 December 2026 to 1 January 2027. Laboratory make-up sessions for students
with approved medical leave are scheduled in the first week of December.
"""),

"hostel-allotment-round-2": ("""---
title: Hostel allotment list, round 2 with document verification slots
date: 2026-08-06
kind: circular
source: Circulars, page 4
---

# Hostel allotment round 2

The round 2 hostel allotment list for the academic year 2026-27 is published on the notice
board and the student portal. Allotment is based on distance from the institute, followed by
merit in the previous examination.

# Document verification

Students in the round 2 list must report for document verification between 11 August and
14 August 2026 at the Hostel Office, according to the slot printed against the roll number.
A student who misses the allotted slot loses the seat to the waiting list.

# Documents required

Bring the allotment letter, a domicile or distance proof, the previous semester mark sheet,
one passport photograph, and the fee receipt for the hostel deposit of Rs. 5,000. The deposit
is refundable at the end of the academic year after a room condition check.

# Hostel fee

The annual hostel fee for 2026-27 is Rs. 62,000 for a two-seater room and Rs. 48,000 for a
three-seater room. Mess charges are billed separately every month and are not part of this fee.
"""),

"scholarship-freeship-ebc": ("""---
title: Government scholarship portal, freeship and EBC application dates
date: 2026-08-02
kind: circular
source: Circulars, page 5
---

# Government scholarship portal

Applications for government scholarship, freeship and the EBC concession for 2026-27 are open
on the state scholarship portal from 1 August 2026. The last date to submit a fresh
application is 30 September 2026 and the last date for renewal is 15 September 2026.

# Eligibility

The EBC concession applies where the annual family income is below Rs. 8,00,000 and the
student has no gap year beyond one year. Freeship applies to categories notified by the state
government. A student may hold only one government scholarship at a time.

# Documents required

Income certificate issued within the last twelve months, caste certificate where applicable,
the previous year mark sheet, an Aadhaar linked bank account, and the institute fee receipt.
Scanned copies must be under 200 KB per file.

# Verification at the institute

After online submission the student must submit the printed application with the documents to
the Scholarship Section, Room 12, within seven days. Applications not verified at the institute
are treated as incomplete and are not forwarded to the department.
"""),

"attendance-detention": ("""---
title: Notice regarding attendance shortfall and detention criteria
date: 2026-07-29
kind: circular
source: Circulars, page 5
---

# Attendance shortfall and detention

A student must have at least 75 percent attendance in every subject to be eligible for the end
semester examination. Attendance is counted separately for theory and for laboratory work.

# Condonation

The head of department may condone a shortfall down to 65 percent where the student produces a
medical certificate, a hospital record, or proof of participation in an institute approved
event. Condonation below 65 percent is not permitted at the department level.

# Detention

A student who remains below the required attendance after condonation is detained in that
subject and cannot appear for the end semester examination in it. A detained student repeats
the subject when it is next offered and pays the repeat registration fee.

# Warning letters

Attendance is reviewed in the last week of every month. Students below 75 percent receive a
warning letter, and a copy is sent to the parent or guardian on record.
"""),

"te-syllabus-revision": ("""---
title: Third-year syllabus revision, subject codes and credit changes
date: 2026-07-25
kind: circular
source: Circulars, page 6
---

# Third-year syllabus revision

The third-year syllabus is revised with effect from the academic year 2026-27. The revision
changes subject codes, redistributes credits, and replaces two electives.

# Credit changes

The total credits for Semester V change from 22 to 21. The Machine Learning course moves from
4 credits to 3 credits with one credit shifted to the associated laboratory. The Semester VI
total is unchanged at 21 credits.

# Subject code changes

Natural Language Processing is now AI5CO3 and was previously AI5CO4. Language Modeling and
Text Analytics is now AI5DE2 and was previously AI5DE1. Deep Learning keeps the code AI5CO2.
The laboratory course codes carry the suffix LR in place of LB.

# Students with backlogs

A student carrying a backlog in a replaced subject appears under the old code and the old
syllabus for two more attempts. After that the student is assessed under the equivalent new
subject notified by the department.
"""),

"fee-structure-2026-27": ("""---
title: Institute fee structure 2026-27 for all programmes
date: 2026-07-21
kind: circular
source: Circulars, page 6
---

# Institute fee structure 2026-27

The fee structure below is for the academic year 2026-27 and covers all programmes. Amounts
are per year unless stated otherwise.

# Undergraduate programmes

B.E. tuition fee is Rs. 1,45,000 per year for the open category and Rs. 72,500 per year for
students holding an approved freeship. The development fee is Rs. 12,000 per year. The one
time admission fee is Rs. 5,000 and the refundable caution deposit is Rs. 10,000.

# Postgraduate programmes

M.E. tuition fee is Rs. 96,000 per year. The laboratory and library charge is Rs. 8,000 per
year. Research scholars registered for a Ph.D. pay Rs. 45,000 per year until submission.

# Other charges

Examination fee is Rs. 2,200 per semester. The transcript fee is Rs. 750 per copy. The
duplicate identity card charge is Rs. 200. Fees are revised only with the approval of the
governing body and any revision is notified before the start of the academic year.
"""),

"revaluation-procedure": ("""---
title: Revaluation application procedure and prescribed fees
date: 2026-07-18
kind: circular
source: Circulars, page 7
---

# Revaluation application procedure

A student who is not satisfied with the result of a theory paper may apply for photocopy of
the answer book, for revaluation, or for both. Applications are made on the student portal
under Examination, Post Result Services.

# Timeline

The application window opens on the day the result is declared and closes on the tenth working
day after declaration. Late applications are not accepted. The revaluation result is declared
within thirty working days of the closing date.

# Prescribed fees

Photocopy of an answer book is Rs. 400 per paper. Revaluation is Rs. 800 per paper.
Where both are applied for together the charge is Rs. 1,000 per paper. The fee is refunded in
full if the revised marks differ from the original by ten percent or more of the maximum marks.

# What changes

The revised mark replaces the original mark whether it is higher or lower. A revaluation
result is final and no second revaluation is permitted for the same paper.
"""),

"academic-calendar-2026-27": ("""---
title: Academic calendar 2026-27
date: 2026-07-01
kind: page
source: Academics, Academic Calendar
---

# Academic calendar 2026-27

The academic year is divided into an odd semester and an even semester. The odd semester runs
from August to December 2026 and the even semester runs from January to May 2027.

# Odd semester

Teaching begins 3 August 2026. Internal assessments are held in September and October.
Practical examinations begin 24 November 2026 and theory examinations begin 8 December 2026.
Results are declared by the second week of January 2027.

# Even semester

Teaching begins 12 January 2027. Internal assessments are held in February and March.
Practical examinations begin 19 April 2027 and theory examinations begin 3 May 2027.
The summer term for backlog subjects runs through June 2027.

# Attendance and eligibility

Attendance is recorded from the first day of teaching. Eligibility for the end semester
examination requires 75 percent attendance in each subject, subject to the condonation rules
notified separately.
"""),

"examination-timetable": ("""---
title: Examination timetable and examination rules
date: 2026-07-05
kind: page
source: Examination, Timetable
---

# Examination timetable

The detailed end semester timetable is published at least three weeks before the first paper.
Theory papers for the odd semester 2026-27 begin on 8 December 2026. Morning papers start at
10:30 and afternoon papers start at 14:30.

# Hall ticket

The hall ticket is released on the student portal seven days before the first paper. A student
is admitted to the examination hall only with a printed hall ticket and the institute identity
card. The hall ticket is issued only when the tuition fee and the examination fee are cleared.

# Examination rules

Students must be seated fifteen minutes before the start. Entry is not permitted after thirty
minutes from the start and no student may leave in the first sixty minutes. Only a non
programmable calculator is allowed where the question paper permits it. Mobile phones,
smart watches and loose paper are not allowed in the hall.

# Unfair means

A case of unfair means is referred to the examination committee. Depending on the finding the
committee may cancel the paper, cancel the full examination, or debar the student from one or
more subsequent examinations.
"""),

"student-handbook": ("""---
title: Student handbook
date: 2026-06-20
kind: handbook
source: Students, Handbook
---

# Section 4.1 Registration

Every student registers for the semester within the first week of teaching. Registration
requires the tuition fee receipt and the clearance of any pending library or laboratory dues.

# Section 4.2 Attendance

A student must maintain at least 75 percent attendance in every theory and laboratory course
to be eligible for the end semester examination. Attendance below this level is reviewed by
the head of department, who may condone a shortfall down to 65 percent against a medical
certificate or proof of institute approved activity. A student who stays below the required
level after condonation is detained in that course and repeats it when it is next offered.

# Section 4.3 Keep Term rules

A student is allowed to carry a Keep Term backlog to the next semester. Admission to the third
year requires clearing all first year subjects and at least half the second year subjects.
A backlog subject is attempted under the syllabus in force at the time it was first registered,
for a maximum of two further attempts.

# Section 5.1 Code of conduct

Ragging in any form leads to immediate suspension and a report to the police under the state
anti ragging law. Damage to institute property is charged to the student along with a fine
decided by the discipline committee.

# Section 6.1 Grievance

A student may file a grievance on the portal under Students, Grievance. The committee responds
within ten working days. Complaints about internal marks are first raised with the subject
teacher and then with the head of department.
"""),

"hostel-rules": ("""---
title: Hostel rules and allotment policy
date: 2026-06-15
kind: page
source: Students, Hostel
---

# Allotment policy

Hostel seats are allotted in rounds. Priority is given to students whose home is more than
50 kilometres from the institute, then to merit in the previous examination, then to students
of the first year. A seat is held for the student for the full academic year.

# Rooms and fee

Two-seater rooms are Rs. 62,000 per year and three-seater rooms are Rs. 48,000 per year.
A refundable deposit of Rs. 5,000 is collected at allotment. Mess charges are billed monthly
and average Rs. 4,200 per month.

# Rules of residence

Entry to the hostel closes at 22:30. Overnight leave requires a written request from the
parent or guardian recorded in the hostel office. Cooking appliances, heaters and any form of
open flame are not permitted in rooms.

# Vacating a seat

A student vacating mid year forfeits the deposit unless the request is approved on medical
grounds. Rooms are inspected at the end of the year and repair charges, if any, are deducted
from the deposit before refund.
"""),

"certificates": ("""---
title: Bonafide certificate, transcripts and other student documents
date: 2026-06-10
kind: page
source: Students, Downloads
---

# Bonafide certificate

A bonafide certificate is issued from the Student Section on request through the portal. The
certificate is issued within three working days and there is no charge for the first two
copies in an academic year. Additional copies are Rs. 100 each.

# Transcript

An official transcript is issued for higher studies and visa purposes. The fee is Rs. 750 per
copy and the issue time is ten working days. A sealed and signed envelope is provided on
request at no extra charge.

# Migration and leaving certificate

The migration certificate is issued after the final result is declared and all dues are
cleared. The leaving certificate is issued once, free of charge, and a duplicate copy is
Rs. 500.

# Identity card

A lost identity card is replaced on payment of Rs. 200 with a copy of the complaint
acknowledgement. The replacement is issued within five working days.
"""),

"library": ("""---
title: Library services and rules
date: 2026-06-05
kind: page
source: Library
---

# Timings

The library is open from 08:30 to 20:00 on working days and from 09:00 to 14:00 on Saturdays.
During the examination period the reading hall stays open until 23:00.

# Borrowing

An undergraduate student may borrow four books at a time for fourteen days. A postgraduate
student may borrow six books for twenty one days. Reference books and the current issue of a
journal are for reading in the library only.

# Overdue and loss

The overdue charge is Rs. 5 per book per day. A lost book is replaced by the student or
charged at twice the current price. Library dues must be cleared before the hall ticket for
the end semester examination is issued.

# Digital resources

The library subscribes to IEEE Xplore, Springer Link and the national digital library
consortium. Off campus access is available through the institute login on the library page.
"""),

"about-institute": ("""---
title: About the institute
date: 2026-05-30
kind: page
source: About Us
---

# About the institute

The Institute of Engineering and Technology has completed sixty years of engineering
education. It is affiliated to the University, accredited by NAAC, and approved by the
technical education council.

# Departments

The institute has eight departments offering undergraduate, postgraduate and doctoral
programmes. Undergraduate programmes are offered in Computer Engineering, Information
Technology, Electronics and Telecommunication, Artificial Intelligence and Machine Learning,
Mechanical Engineering, Civil Engineering, Electrical Engineering and Instrumentation.

# Campus

The campus has departmental laboratories, a central computing facility, a library, a sports
complex and separate hostels for men and women. The institute runs an incubation cell for
student startups.

# Administration

The institute is governed by a governing body chaired by the trust nominee. The principal is
the head of the institute and is assisted by the deans of academics, student affairs and
research.
"""),

"admissions-2026": ("""---
title: Admissions 2026
date: 2026-05-20
kind: page
source: Admissions
---

# Undergraduate admission

Admission to the first year of the B.E. programme is through the state common entrance test
followed by the centralised admission process. A candidate must have passed the higher
secondary examination with Physics, Mathematics and one of Chemistry, Biology, Computer
Science or Technical Vocational subject, with at least 45 percent marks in these subjects.

# Direct second year admission

Diploma holders are admitted directly to the second year against the notified lateral entry
seats. Eligibility requires a diploma in a relevant branch with at least 45 percent marks.

# Postgraduate admission

Admission to the M.E. programme is through the state postgraduate entrance test. Candidates
with a valid GATE score are considered first against the notified seats.

# Important dates

The centralised admission process for 2026-27 runs from 15 June to 25 July 2026. Institute
level vacancy round admissions close on 10 August 2026. Documents are verified at the
admission cell between 10:00 and 16:00 on working days.
"""),

"departments-aiml": ("""---
title: Department of Artificial Intelligence and Machine Learning
date: 2026-05-15
kind: page
source: Departments
---

# Department of Artificial Intelligence and Machine Learning

The department offers a four year B.E. programme with an intake of sixty students. It was
started in 2020 and has laboratories for machine learning, natural language processing and
computer vision.

# Curriculum

The third year covers Deep Learning, Natural Language Processing, Language Modeling and Text
Analytics, and Machine Design of Data Systems. The fourth year has two elective slots and a
year long project.

# Laboratories

The department runs four laboratories with GPU workstations, a shared cluster for training
runs, and licensed access to standard data science tools. Laboratory hours are allotted per
batch and are published with the timetable.

# Projects and internships

Every student completes a mini project in the third year and a major project in the fourth
year. The department coordinates summer internships with partner companies and startups
through the training and placement cell.
"""),

"placements": ("""---
title: Training and placement
date: 2026-05-10
kind: page
source: Placements
---

# Placement process

The placement season for the 2026-27 batch begins in August 2026. A student registers with the
training and placement cell before appearing for any company process. Registration requires an
updated resume approved by the department coordinator.

# Eligibility

A student with more than two live backlogs is not eligible for the campus process. A student
who accepts an offer is out of the process for further companies, except where the offer is
withdrawn by the company.

# Preparation

The cell runs aptitude, group discussion and technical interview preparation sessions through
the odd semester. Attendance in these sessions is recorded and shared with the department.

# Records

In the previous year one hundred and eighty two students were placed across forty one
recruiters. The highest package was Rs. 24 lakh per year and the median package was
Rs. 6.5 lakh per year.
"""),

"contact": ("""---
title: Contact and office hours
date: 2026-05-01
kind: page
source: Contact
---

# Contact

The institute office is open from 09:30 to 17:30 on working days and from 09:30 to 13:30 on
Saturdays. The office is closed on the second and fourth Saturday of every month.

# Sections

The Accounts Section is in Room 104 and handles fees, refunds and failed transactions. The
Examination Section is in Room 210 and handles hall tickets, results and revaluation. The
Student Section is in Room 12 and handles certificates, scholarships and hostel matters.

# Reaching the campus

The campus is a fifteen minute walk from the suburban railway station and is served by four
bus routes. Visitor parking is available at the main gate on production of an identity proof.

# Grievance

A grievance may be filed on the student portal or in writing to the dean of student affairs.
The anti ragging committee and the internal complaints committee contact details are displayed
at the entrance of every building.
"""),
}

for name, body in DOCS.items():
    (SEED / f"{name}.md").write_text(body.lstrip(), encoding="utf-8")

print(f"wrote {len(DOCS)} seed documents to {SEED}")
