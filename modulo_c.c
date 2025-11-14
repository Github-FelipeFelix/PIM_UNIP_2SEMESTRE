// Arquivo: modulo_c.c
// Função: Atualizar notas do arquivo binário com a lista de RAs
// Objetivo: Garantir que o binário tenha só os RAs do texto

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINHA 15
#define ARQ_BIN "dados_notas.dat"
#define ARQ_RAS "ras_para_c.txt"
#define ARQ_TEMP "dados_temp.dat"

// Estrutura do aluno
struct Notas {
    int ra;
    float np1;
    float np2;
    float pim;
};

int main() {
    FILE *f_ras, *f_bin, *f_temp;
    struct Notas aluno;
    struct Notas novo_aluno;
    char linha[MAX_LINHA];
    int ra_texto;

    f_ras = fopen(ARQ_RAS, "r");
    if (!f_ras) return 0; // se nao existe lista, sai

    f_bin = fopen(ARQ_BIN, "rb");
    f_temp = fopen(ARQ_TEMP, "wb");

    int bin_existe = (f_bin != NULL);

    while (fgets(linha, sizeof(linha), f_ras)) {
        linha[strcspn(linha, "\n")] = 0; // tira \n
        ra_texto = atoi(linha);

        int achei = 0;

        if (bin_existe) {
            rewind(f_bin);
            while (fread(&aluno, sizeof(struct Notas), 1, f_bin)) {
                if (aluno.ra == ra_texto) {
                    fwrite(&aluno, sizeof(struct Notas), 1, f_temp);
                    achei = 1;
                    break;
                }
            }
        }

        if (!achei) {
            novo_aluno.ra = ra_texto;
            novo_aluno.np1 = 0;
            novo_aluno.np2 = 0;
            novo_aluno.pim = 0;
            fwrite(&novo_aluno, sizeof(struct Notas), 1, f_temp);
        }
    }

    fclose(f_ras);
    if (f_bin) fclose(f_bin);
    fclose(f_temp);

    rename(ARQ_TEMP, ARQ_BIN);

    return 0;
}
