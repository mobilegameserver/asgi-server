import os.path


def main():
    files = ['.env', '.env.dev', '.env.beta']
    required_keys = ['PHASE', 'AES_KEY', 'USERS_DB_URL', 'SERVICES_DB_URL', 'STATISTICS_DB_URL']

    error_found = 0
    for file in files:  # , '.env.prod']:
        with open(os.path.join('..', file), 'r') as f:
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

    if error_found == 0:
        print('\nOK')


if __name__ == '__main__':
    main()
