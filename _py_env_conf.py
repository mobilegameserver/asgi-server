import os.path


def main():
    file = '.env'

    if not os.path.exists(file):
        print('\nplease copy "./.env.dev" to "{}"\n'.format(file))
        return

    required_keys = ['PHASE', 'AES_KEY', 'USERS_DB_URL', 'SERVICES_DB_URL', 'STATISTICS_DB_URL']

    error_found = 0
    with open(file, 'r') as f:
        lines = f.readlines()

    env_keys = []
    for line in lines:
        line_strip = line.strip()
        if line_strip == '' or line_strip[0] == '#':
            continue

        line_split = line_strip.split('=')
        if len(line_split) != 2:
            print('invalid line in .env: ' + line)

        k = line_split[0].strip()
        k = k.strip('"')
        k = k.strip("'")

        env_keys.append(k)

    for k in required_keys:
        if k not in env_keys:
            print('{} not found in {}'.format(k, file))
            error_found += 1

    p = './conf/conf.py'
    if not os.path.exists(p):
        print('\nplease copy "./conf/conf_dev.py" to "{}"\n'.format(p))
        return

    if error_found == 0:
        print('\nOK\n')


if __name__ == '__main__':
    main()
