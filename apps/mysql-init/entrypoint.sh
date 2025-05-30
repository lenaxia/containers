#!/usr/bin/env bash

export INIT_MYSQL_SUPER_USER=${INIT_MYSQL_SUPER_USER:-root}
export INIT_MYSQL_PORT=${INIT_MYSQL_PORT:-3306}
export INIT_MYSQL_UTF8=${INIT_MYSQL_UTF8:-"false"}

if [[ -z "${INIT_MYSQL_HOST}"       ||
      -z "${INIT_MYSQL_SUPER_PASS}" ||
      -z "${INIT_MYSQL_USER}"       ||
      -z "${INIT_MYSQL_PASS}"       ||
      -z "${INIT_MYSQL_DBNAME}"
]]; then
    printf "\e[1;32m%-6s\e[m\n" "Invalid configuration - missing a required environment variable"
    [[ -z "${INIT_MYSQL_HOST}" ]]       && printf "\e[1;32m%-6s\e[m\n" "INIT_MYSQL_HOST: unset"
    [[ -z "${INIT_MYSQL_SUPER_PASS}" ]] && printf "\e[1;32m%-6s\e[m\n" "INIT_MYSQL_SUPER_PASS: unset"
    [[ -z "${INIT_MYSQL_USER}" ]]       && printf "\e[1;32m%-6s\e[m\n" "INIT_MYSQL_USER: unset"
    [[ -z "${INIT_MYSQL_PASS}" ]]       && printf "\e[1;32m%-6s\e[m\n" "INIT_MYSQL_PASS: unset"
    [[ -z "${INIT_MYSQL_DBNAME}" ]]     && printf "\e[1;32m%-6s\e[m\n" "INIT_MYSQL_DBNAME: unset"
    exit 1
fi

export MYSQL_PWD="${INIT_MYSQL_SUPER_PASS}"

until mysqladmin ping --host="${INIT_MYSQL_HOST}" --user="${INIT_MYSQL_SUPER_USER}"; do
    printf "\e[1;32m%-6s\e[m\n" "Waiting for Host '${INIT_MYSQL_HOST}' ..."
    sleep 1
done

user_exists=$(\
    mysql \
        --host="${INIT_MYSQL_HOST}" \
        --user="${INIT_MYSQL_SUPER_USER}" \
        --execute="SELECT 1 FROM mysql.user WHERE user = '${INIT_MYSQL_USER}'"
)

if [[ -z "${user_exists}" ]]; then
    printf "\e[1;32m%-6s\e[m\n" "Create User ${INIT_MYSQL_USER} ..."
    mysql --host="${INIT_MYSQL_HOST}" --user="${INIT_MYSQL_SUPER_USER}" --execute="CREATE USER ${INIT_MYSQL_USER}@'%' IDENTIFIED BY '${INIT_MYSQL_PASS}';"
fi

for dbname in ${INIT_MYSQL_DBNAME}; do
    database_exists=$(\
        mysql \
            --host="${INIT_MYSQL_HOST}" \
            --user="${INIT_MYSQL_SUPER_USER}" \
            --execute="SELECT 1 FROM information_schema.schemata WHERE schema_name = '${dbname}'"
    )
    if [[ -z "${database_exists}" ]]; then
        if [[ "${INIT_MYSQL_UTF8}" == "true" ]]; then
            printf "\e[1;32m%-6s\e[m\n" "Create Database ${dbname} with UTF8 encoding ..."
            mysql --host="${INIT_MYSQL_HOST}" --user="${INIT_MYSQL_SUPER_USER}" \
                --execute="CREATE DATABASE IF NOT EXISTS ${dbname} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        else
            printf "\e[1;32m%-6s\e[m\n" "Create Database ${dbname} ..."
            mysql --host="${INIT_MYSQL_HOST}" --user="${INIT_MYSQL_SUPER_USER}" \
                --execute="CREATE DATABASE IF NOT EXISTS ${dbname};"
        fi
        
        database_init_file="/initdb/${dbname}.sql"
        if [[ -f "${database_init_file}" ]]; then
            printf "\e[1;32m%-6s\e[m\n" "Initialize Database ..."
            mysql \
                --host="${INIT_MYSQL_HOST}" \
                --user="${INIT_MYSQL_SUPER_USER}" \
                --database="${dbname}" \
                < "${database_init_file}"
        fi
    fi
    printf "\e[1;32m%-6s\e[m\n" "Update User Privileges on Database ..."
    mysql --host="${INIT_MYSQL_HOST}" --user="${INIT_MYSQL_SUPER_USER}" \
        --execute="GRANT ALL PRIVILEGES ON ${dbname}.* TO '${INIT_MYSQL_USER}'@'%'; FLUSH PRIVILEGES;"
done
