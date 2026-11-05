#! /bin/sh

##########################
# INIT
##########################

# the parent directory containing everything about this grading job
JOB_DIR="${1:-/grade}"

if [ ! -d "$JOB_DIR" ]; then
    echo "ERROR: $JOB_DIR not found! Mounting may have failed."
    exit 1
fi

# the job subdirectories
STUDENT_DIR=$JOB_DIR'/student'
TEST_DIR=$JOB_DIR'/tests'
OUT_DIR=$JOB_DIR'/results'
DATA_DIR=$JOB_DIR'/data'

# where we will copy everything
MERGE_DIR=$JOB_DIR'/run'

# now set up the stuff so that our run.sh can work
mkdir $MERGE_DIR
mkdir $MERGE_DIR/test_student
mkdir $OUT_DIR

# Move the entire student directory as 'student/' inside the data directory.
# This preserves subdirectory structure for workspace questions (e.g. utils/, models/)
# and keeps the student files at a predictable path for single-file questions.
mv "$STUDENT_DIR" "$MERGE_DIR/test_student/student"
# TODO this has some pretty hardcoded assumptions about file names. Discuss in meeting
# what the best way to change this is
mv $TEST_DIR/* $MERGE_DIR/test_student/
mv $MERGE_DIR/test_student/test_student.py $MERGE_DIR/test_student.py

# PrairieLearn writes data.json to the data directory, and pytest is told to read it from there.
# It can hold correct_answers, so it's for the grader only. It must be owned by root with
# owner-only modes: student code keeps root's supplementary groups, and its uid may match the owner
# of files mounted from the host.
protect_data_json() {
    if [ "$(id -u)" = 0 ]; then
        chown -R root:root "$DATA_DIR" || return 1
    fi
    chmod 700 "$DATA_DIR" && chmod 600 "$DATA_DIR/data.json"
}

if [ -f "$DATA_DIR/data.json" ] && ! protect_data_json; then
    echo '{"succeeded": false, "score": 0.0, "message": "The autograder could not protect its grading data. Please contact course staff and have them check the logs for this submission."}' > "$OUT_DIR/results.json"
    echo "ERROR: could not protect $DATA_DIR/data.json"
    exit 1
fi

# Do not allow ag user to modify, rename, or delete any existing files
#chmod -R 755 "$MERGE_DIR"
#chmod 1777 "$MERGE_DIR"

##########################
# RUN
##########################

echo "[run] starting autograder"

# run the autograder as a limited user called ag
# Pass --data-json-path with '=': pytest's first pass over the arguments, before plugin options are
# registered, would treat a separate value as a test path.
# Use --worker-username to drop privileges to the 'ag' user in the student code sandbox
uv run pytest -p prairielearn-grader --color=no --log-cli-level=DEBUG --worker-username ag --data-json-path="$DATA_DIR/data.json" "$MERGE_DIR"

# TODO change the default output name
mv "$MERGE_DIR/autograder_results.json" "$OUT_DIR/results.json"

# if that didn't work, then print a last-ditch message
if [ ! -s $OUT_DIR/results.json ]; then
    echo '{"succeeded": false, "score": 0.0, "message": "Your code could not be processed by the autograder. Please contact course staff and have them check the logs for this submission."}' > $OUT_DIR/results.json
fi

echo "[run] autograder completed"
